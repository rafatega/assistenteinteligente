from app.models.receive_message import WebhookMessage
from app.services.openai_service import extract_message_content
from app.services.funnel_orchestrator import fetch_account_data, process_user_funnel
from app.utils.logger import logger
from app.utils.message_aggregator import debounce_and_collect

async def conversation_pipeline(webhook: WebhookMessage, tempo_espera_debounce: int) -> dict:

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
    
    agrupado = await debounce_and_collect(webhook.phone, webhook.connectedPhone, mensagem, tempo_espera_debounce)

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
    account_data = await fetch_account_data(webhook.connectedPhone)
    conversation =  await conversation_pipeline(webhook, account_data.tempo_espera_debounce)
    logger.info(f"[📬 MENSAGEM RECEBIDA] {conversation['numero']} - {conversation['telefone_empresa']}: {conversation['mensagem']}")

    # Só processa se a mensagem não for do próprio bot/assistente
    if not conversation['from_me']:
        #funnel_result = await process_user_funnel(conversation['mensagem'], conversation['numero'], conversation['telefone_empresa'], conversation['nome_cliente'])
        logger.info(f"[🚀 FUNIL PROCESSADO] {conversation['numero']} - {conversation['telefone_empresa']}: {conversation['mensagem']}")
        logger.info(f"[📦 RESULTADO FUNIL] {account_data}")
    else:
        logger.info(f"[🔕 IGNORADO] Mensagem do próprio bot/assistente: {conversation['numero']} - {conversation['telefone_empresa']}")


