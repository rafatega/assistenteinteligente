from app.models.receive_message import WebhookMessage
from app.services.openai_service import extract_message_content
from app.utils.logger import logger
from app.utils.message_aggregator import debounce_and_collect

async def process_message(body: dict) -> dict:
    webhook = WebhookMessage(**body)
    mensagem = await extract_message_content(webhook)

    if not mensagem or webhook.isGroup:
        return {"status": "ignored"}

    agrupado = await debounce_and_collect(webhook.phone, webhook.connectedPhone, mensagem)
    
    logger.info(f"[✅ MENSAGEM RECEBIDA] {webhook.phone} - {webhook.connectedPhone}: {agrupado} | {webhook.momment} | {webhook.senderName} | isGroup: {webhook.isGroup} | fromMe: {webhook.fromMe}")
    
    return {
    "mensagem": agrupado,
    "numero": webhook.phone,
    "telefone_empresa": webhook.connectedPhone,
    "momento": webhook.momment,
    "nome_cliente": webhook.senderName,
    "is_group": webhook.isGroup,
    "from_me": webhook.fromMe
    }