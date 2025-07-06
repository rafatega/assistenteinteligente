from app.models.receive_message import WebhookMessage
from app.services.openai_service import extract_message_content
from app.utils.logger import logger

async def process_message(body: dict) -> dict:
    # Transforma o dict bruto em objeto tipado
    received_webhook = WebhookMessage(**body)
    logger.info(f"{received_webhook}")

    mensagem = await extract_message_content(received_webhook)
    numero = received_webhook.phone
    telefone_empresa = received_webhook.connectedPhone
    momento = received_webhook.momment
    nome_cliente = received_webhook.senderName
    is_group = received_webhook.isGroup
    from_me = received_webhook.fromMe

    #logger.info(f"[PROCESSANDO MENSAGEM] Mensagem: {mensagem}, numero: {numero}, telefone_empresa: {telefone_empresa}, momento: {momento}, nome_cliente: {nome_cliente}, is_group: {is_group}, from_me: {from_me}")

    # Chave composta cliente + empresa
    debounce_key = f"{numero}:{telefone_empresa}"






    return {"status": "ok"}
