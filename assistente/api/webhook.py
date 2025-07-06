from fastapi import APIRouter, Request
from assistente.servicos.processar_mensagem import process_incoming_message

router = APIRouter()

@router.post("/webhook")
async def receber_mensagem(request: Request):
    body = await request.json()
    return await process_incoming_message(body)

@router.get("/ping")
def ping():
    return {"pong": True}