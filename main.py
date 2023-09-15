from fastapi import FastAPI
from logging_config import setup_logging
import logging
import sys

app = FastAPI()

setup_logging()
logger = logging.getLogger(__name__)


@app.get("/")
async def root():
    return {"message": "Hello World"}


@app.get("/hello/{name}")
async def say_hello(name: str):
    return {"message": f"Hello {name}"}
