from app.models.receive_message import WebhookMessage
from app.services.pipeline_functions import fetch_account_data, conversation_pipeline
from app.utils.logger import logger

async def process_message(body: dict) -> dict:
    webhook = WebhookMessage(**body)
    account_data = await fetch_account_data(webhook.connectedPhone)
    conversation =  await conversation_pipeline(webhook, account_data.tempo_espera_debounce)

    # Só processa se a mensagem não for do próprio bot/assistente
    if not conversation['from_me']:
        #funnel_result = await process_user_funnel(conversation['mensagem'], conversation['numero'], conversation['telefone_empresa'], conversation['nome_cliente'])
        logger.info(f"[🚀 ACCOUNT DATA]\n {account_data} \n[🚀 ACCOUNT DATA]")
        logger.info(f"[🚀 CONVERSATION PIPELINE]\n {conversation} \n[🚀 CONVERSATION PIPELINE]")
        
    else:
        logger.info(f"[🔕 IGNORADO] Mensagem do próprio bot/assistente: {conversation['numero']} - {conversation['telefone_empresa']}")


