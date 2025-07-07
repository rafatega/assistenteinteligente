from app.models.receive_message import WebhookMessage
from app.services.openai_service import extract_message_content
from app.utils.logger import logger
from app.utils.message_aggregator import debounce_and_collect

async def conversation_pipeline(webhook: WebhookMessage) -> dict:

    # Extrai mensagem e limpa espaços
    mensagem = await extract_message_content(webhook)

    # Proteção real: nunca chama debounce se mensagem não for válida
    if not mensagem:
        logger.info(f"[🔕 IGNORADO] Mensagem vazia | {webhook.phone}")
        return {
            "status": "ignored",
            "mensagem": "",
            "numero": webhook.phone,
            "telefone_empresa": webhook.connectedPhone,
            "momento": webhook.momment,
            "nome_cliente": webhook.senderName,
            "is_group": webhook.isGroup,
            "from_me": webhook.fromMe
        }
    
    agrupado = await debounce_and_collect(webhook.phone, webhook.connectedPhone, mensagem)

    return {
        "status": "ok",
        "mensagem": agrupado,
        "numero": webhook.phone,
        "telefone_empresa": webhook.connectedPhone,
        "momento": webhook.momment,
        "nome_cliente": webhook.senderName,
        "is_group": webhook.isGroup,
        "from_me": webhook.fromMe
    }

async def process_message(body: dict) -> dict:
    webhook = WebhookMessage(**body)
    logger.info(f"[📬 WEBHOOK] {webhook}")
    conversation =  await conversation_pipeline(webhook)
    logger.info(f"[📬 MENSAGEM RECEBIDA] {conversation['numero']} - {conversation['telefone_empresa']}: {conversation['mensagem']}")
    return conversation

