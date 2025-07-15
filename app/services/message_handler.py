import time
from app.models.receive_message import WebhookMessage
from app.services.pipeline_functions import fetch_config_info, fetch_history_info, fetch_funnel_info, webhook_treatment, fetch_user_info, calculate_user_info
from app.utils.logger import logger

async def process_message(body: dict) -> dict:
    start_time = time.monotonic()

    webhook = WebhookMessage(**body)
    config_info = await fetch_config_info(webhook.connectedPhone)
    history_info = await fetch_history_info(webhook.connectedPhone, webhook.phone)
    webhook_info =  await webhook_treatment(webhook, config_info.tempo_espera_debounce)
    funnel_info = await fetch_funnel_info(webhook.connectedPhone)
    user_info = await fetch_user_info(webhook.connectedPhone, webhook.phone, funnel_info)
    updated_user_info, updated_prompt = await calculate_user_info(webhook_info.mensagem, user_info, funnel_info, webhook.connectedPhone, webhook.phone)

    # Só processa se a mensagem não for do próprio bot/assistente
    if not webhook_info.fromMe:
        #funnel_result = await process_user_funnel(conversation['mensagem'], conversation['numero'], conversation['telefone_empresa'], conversation['nome_cliente'])
        logger.info(f"[🚀 CONFIG_INFO ]\n {config_info} \n[🚀 CONFIG_INFO ]")
        logger.info(f"[🚀 HISTORY_INFO ]\n {webhook_info} \n[🚀 HISTORY_INFO ]")
        logger.info(f"[🚀 WEBHOOK_INFO ]\n {webhook_info} \n[🚀 WEBHOOK_INFO ]")
        #logger.info(f"[🚀 FUNNEL INFO ]\n {funnel_info} \n[🚀 FUNNEL INFO ]")
        logger.info(f"[🚀 USER INFO ]\n {user_info} \n[🚀 USER INFO ]")
        logger.info(f"[🚀 UPDATED USER INFO ]\n {updated_user_info} \n[🚀 UPDATED USER INFO ]")
        logger.info(f"[🚀 UPDATED PROMPT ]\n {updated_prompt} \n[🚀 UPDATED PROMPT ]")
        
    else:
        logger.info(f"[🔕 IGNORADO] Mensagem do próprio bot/assistente: {webhook_info.phone} - {webhook_info.connectedPhone}")
    
    elapsed = time.monotonic() - start_time
    logger.info(f"[⏱️ Tempo de execução total]: {elapsed:.3f} segundos")


