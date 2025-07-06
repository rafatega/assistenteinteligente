from app.models.receive_message import WebhookMessage
from app.services.openai_service import extract_message_content
from app.utils.logger import logger
from app.utils.message_aggregator import debounce_and_collect

async def process_message(body: dict) -> dict:
    webhook = WebhookMessage(**body)

    # Extrai mensagem e limpa espaços
    mensagem_raw = await extract_message_content(webhook)
    mensagem = (mensagem_raw or "").strip()

    # Proteção real: nunca chama debounce se mensagem não for válida
    if not mensagem:
        logger.info(f"[🔕 IGNORADO] Mensagem vazia | {webhook.phone}")
        return {"status": "ignored"}

    if webhook.isGroup or webhook.fromMe:
        logger.info(f"[🔕 IGNORADO] Grupo ou enviada por mim | {webhook.phone}")
        return {"status": "ignored"}

    logger.info(f"[➡️ ENVIANDO PARA DEBOUNCE] {mensagem!r} de {webhook.phone}")
    agrupado = await debounce_and_collect(webhook.phone, webhook.connectedPhone, mensagem)

    logger.info(
        f"[✅ MENSAGEM AGRUPADA] {webhook.phone} - {webhook.connectedPhone}: {agrupado} | "
        f"{webhook.momment} | {webhook.senderName} | isGroup: {webhook.isGroup} | fromMe: {webhook.fromMe}"
    )

    return {
        "mensagem": agrupado,
        "numero": webhook.phone,
        "telefone_empresa": webhook.connectedPhone,
        "momento": webhook.momment,
        "nome_cliente": webhook.senderName,
        "is_group": webhook.isGroup,
        "from_me": webhook.fromMe
    }

