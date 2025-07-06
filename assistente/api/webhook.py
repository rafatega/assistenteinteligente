from fastapi import APIRouter, Request
from assistente.servicos.processar_mensagem import processa_mensagem

router = APIRouter()

@router.post("/webhook")
async def receber_mensagem(request: Request):
    body = await request.json()
    return await processa_mensagem(body)

@router.get("/ping")
def ping():
    return {"pong": True}