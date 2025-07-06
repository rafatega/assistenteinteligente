from fastapi import APIRouter, Request
from app.services.message_handler import process_message
from app.utils.logger import logger

router = APIRouter()

@router.post("/webhook")
async def receive_message(request: Request):
    body = await request.json()
    return await process_message(body)
    

@router.get("/ping")
def ping():
    return {"pong": True}