from fastapi import FastAPI
from logging_config import setup_logging
import logging

app = FastAPI()

setup_logging()
logger = logging.getLogger(__name__)

logger.info("This is an info message from fastapi")

@app.get("/")
async def root():
    return {"message": "Hello World"}


@app.get("/hello/{name}")
async def say_hello(name: str):
    return {"message": f"Hello {name}"}
