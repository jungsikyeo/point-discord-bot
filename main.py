import asyncio
import os
from .db_pool import Database
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from web3 import Web3
from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

mysql_ip = os.getenv("MYSQL_IP")
mysql_port = os.getenv("MYSQL_PORT")
mysql_id = os.getenv("MYSQL_ID")
mysql_passwd = os.getenv("MYSQL_PASSWD")
mysql_db = os.getenv("MYSQL_DB")

db = Database(mysql_ip, mysql_port, mysql_id, mysql_passwd, mysql_db)

# Global state variables
class ListenerState:
    is_running: bool = False
    current_block: int = 53383700
    last_processed_block: int = 53383700
    last_event_time: Optional[datetime] = None
    recent_events: List[dict] = []
    max_recent_events: int = 100
    background_task: Optional[asyncio.Task] = None
    batch_task: Optional[asyncio.Task] = None

state = ListenerState()

# 테스트넷
# web3 = Web3(Web3.HTTPProvider("https://rpc.ankr.com/avalanche_fuji"))
# CONTRACT_ADDRESS = web3.to_checksum_address("0x984570351F0CD43e7cC55B5153301F4FD301f424")

# 메인넷
web3 = Web3(Web3.HTTPProvider("https://api.avax.network/ext/bc/C/rpc"))
CONTRACT_ADDRESS = web3.to_checksum_address("0xcFb703b39F3C2b08A74E35BB8Cf1296B5F5Cf8a8")

EVENT_SIGNATURE = "0x" + web3.keccak(text="NicknameRegistered(address,string)").hex()

contract_abi = [
    {
        "anonymous": False,
        "inputs": [
            {
                "indexed": True,
                "internalType": "address",
                "name": "user",
                "type": "address"
            },
            {
                "indexed": False,
                "internalType": "string",
                "name": "nickname",
                "type": "string"
            }
        ],
        "name": "NicknameRegistered",
        "type": "event"
    }
]

contract = web3.eth.contract(address=CONTRACT_ADDRESS, abi=contract_abi)

class NicknameEvent(BaseModel):
    transaction_hash: str
    user: str
    nickname: str
    block_number: int
    timestamp: datetime

class ListenerStatus(BaseModel):
    is_running: bool
    current_block: int
    last_processed_block: int
    last_event_time: Optional[datetime]
    total_events_captured: int


async def save_nickname_event_to_db(event_data: dict):
    """Save nickname event to database with duplicate check"""
    connection = db.get_connection()
    cursor = connection.cursor()
    try:
        # Check if transaction hash already exists
        check_query = """
            SELECT id FROM nickname_tx_maple 
            WHERE transaction_hash = %s
            LIMIT 1
        """
        cursor.execute(check_query, (event_data['transaction_hash'],))
        existing_tx = cursor.fetchone()

        if existing_tx:
            print(f"Transaction {event_data['transaction_hash']} already exists in database, skipping...")
            return False

        # If not exists, insert new record
        insert_query = """
            INSERT INTO nickname_tx_maple 
            (user, nickname, block_number, transaction_hash, timestamp_open, status)
            VALUES (%s, %s, %s, %s, %s, 'OPEN')
        """
        values = (
            event_data['user'],
            event_data['nickname'],
            event_data['block_number'],
            event_data['transaction_hash'],
            event_data['timestamp_open']
        )

        cursor.execute(insert_query, values)
        connection.commit()
        print(f"Saved new event to DB: {event_data['nickname']} for user {event_data['user']}")
        return True

    except Exception as e:
        connection.rollback()
        print(f"Error saving to database: {str(e)}")
        return False
    finally:
        cursor.close()
        connection.close()


async def process_events(events) -> List[dict]:
    """Process blockchain events and return formatted data"""
    nickname_registereds = []
    for event in events:
        try:
            decoded_event = contract.events.NicknameRegistered().process_log(event)

            # Create event data
            nickname_registered = {
                'transaction_hash': event['transactionHash'].hex(),
                'user': decoded_event['args']['user'],
                'nickname': decoded_event['args']['nickname'],
                'block_number': event['blockNumber'],
                'timestamp_open': datetime.now()
            }

            # Save to database and only add to in-memory list if successfully saved
            if await save_nickname_event_to_db(nickname_registered):
                nickname_registereds.append(nickname_registered)
                print(f"Processed new event: {nickname_registered['nickname']} "
                      f"for user {nickname_registered['user']}")
            else:
                print(f"Skipped duplicate or failed event for tx hash: "
                      f"{nickname_registered['transaction_hash']}")

        except Exception as e:
            print(f"Error processing event: {e}")
            continue

    return nickname_registereds


async def get_events_for_blocks(from_block: int, to_block: int) -> List[dict]:
    """Get events for specified block range"""
    try:
        filter_params = {
            'address': CONTRACT_ADDRESS,
            'fromBlock': from_block,
            'toBlock': to_block,
            'topics': [EVENT_SIGNATURE]
        }
        logs = web3.eth.get_logs(filter_params)
        return logs
    except Exception as e:
        print(f"Error getting logs: {str(e)}")
        return []

async def blockchain_listener():
    """Background task for listening to blockchain events"""
    print("Starting blockchain listener...")
    while state.is_running:
        try:
            latest_block = web3.eth.block_number
            to_block = min(
                state.current_block + 10,  # MAX_BLOCK_ON_TIME
                latest_block - 5  # BLOCK_CONFIRM
            )

            if state.current_block <= to_block:
                events = await get_events_for_blocks(state.current_block, to_block)

                if events:
                    new_events = await process_events(events)
                    state.recent_events.extend(new_events)
                    state.recent_events = state.recent_events[-state.max_recent_events:]
                    state.last_event_time = datetime.now()
                    print(f"Found {len(new_events)} events")

                state.last_processed_block = to_block
                state.current_block = to_block + 1

            await asyncio.sleep(3)
        except Exception as e:
            print(f"Error in blockchain listener: {str(e)}")
            await asyncio.sleep(6)  # BLOCK_TIME


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    print("Starting up...")
    state.is_running = True
    # Start both background tasks
    state.background_task = asyncio.create_task(blockchain_listener())
    yield
    # Shutdown
    print("Shutting down...")
    state.is_running = False
    if state.background_task:
        state.background_task.cancel()
        try:
            await state.background_task
        except asyncio.CancelledError:
            pass
    if state.batch_task:
        state.batch_task.cancel()
        try:
            await state.batch_task
        except asyncio.CancelledError:
            pass

app = FastAPI(lifespan=lifespan)

@app.get("/status", response_model=ListenerStatus)
async def get_status():
    """Get the current status of the blockchain listener and batch processor"""
    return ListenerStatus(
        is_running=state.is_running,
        current_block=state.current_block,
        last_processed_block=state.last_processed_block,
        last_event_time=state.last_event_time,
        total_events_captured=len(state.recent_events)
    )


@app.get("/events", response_model=List[NicknameEvent])
async def get_events(limit: int = 10):
    """Get recent nickname registration events"""
    if limit > 100:
        raise HTTPException(status_code=400, detail="Limit cannot exceed 100")
    return state.recent_events[-limit:]


@app.get("/start")
async def start_listener():
    """Start the blockchain listener if it's not running"""
    if not state.is_running:
        state.is_running = True
        if state.background_task is None or state.background_task.done():
            state.background_task = asyncio.create_task(blockchain_listener())
        return {"message": "Blockchain listener started"}
    return {"message": "Blockchain listener is already running"}

@app.get("/stop")
async def stop_listener():
    """Stop the blockchain listener"""
    if state.is_running:
        state.is_running = False
        if state.background_task:
            state.background_task.cancel()
            try:
                await state.background_task
            except asyncio.CancelledError:
                pass
            state.background_task = None
        return {"message": "Blockchain listener stopped"}
    return {"message": "Blockchain listener is not running"}


@app.get("/")
async def root():
    return {"message": "Hello World"}


@app.get("/hello/{name}")
async def say_hello(name: str):
    return {"message": f"Hello {name}"}
