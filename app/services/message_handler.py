from app.models.receive_message import WebhookMessage
from app.services.openai_service import extract_message_content
from app.utils.logger import logger
from app.utils.debouncer import debounce_by_user

@debounce_by_user
async def handle_debounced_messages(phone: str, connectedPhone: str, mensagens: list[str]):
    # Agrupa e processa
    texto_agrupado = ", ".join(mensagens).strip()
    logger.info(f"[🤖 PROCESSANDO GRUPO] {phone}@{connectedPhone}: {texto_agrupado}")
    # Aqui você chama OpenAI, salva histórico, etc.

async def process_message(body: dict) -> dict:
    # Transforma o dict bruto em objeto tipado
    received_webhook = WebhookMessage(**body)
    logger.info(f"{received_webhook}")

    mensagem = await extract_message_content(received_webhook)

    if not mensagem or not received_webhook.phone or not received_webhook.connectedPhone:
        return {"status": "empty"}

    logger.info(f"""[PROCESSANDO MENSAGEM] 
                Mensagem: {mensagem}, 
                numero: {received_webhook.phone}, 
                telefone_empresa: {received_webhook.connectedPhone}, 
                momento: {received_webhook.momment}, 
                nome_cliente: {received_webhook.senderName}, 
                is_group: {received_webhook.isGroup}, 
                from_me: {received_webhook.fromMe}""")

    handle_debounced_messages(received_webhook.phone, received_webhook.connectedPhone, mensagem)





    return {"status": "ok"}
