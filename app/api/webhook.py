from fastapi import APIRouter, Request, BackgroundTasks
from app.services.message_handler import process_message
from app.utils.logger import logger

router = APIRouter()

# Rota para receber webhooks do ZAPI


@router.post("/webhook")
async def receive_message(request: Request, background_tasks: BackgroundTasks):
    try:
        body = await request.json()
        logger.info(f"[📬 WEBHOOK RECEBIDO] {body}")

        # Executar o process_message no fundo
        background_tasks.add_task(process_message, body)

        # Retornar imediatamente para ZAPI
        return {"status": "ok"}

    except Exception as e:
        logger.error(f"❌ Erro ao receber webhook: {e}")
        return {"status": "error", "message": str(e)}


@router.get("/ping")
def ping():
    return {"pong": True}
