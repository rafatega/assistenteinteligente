import time
import openai
from app.config.redis_client import redis_client
from app.config.config import API_KEY_OPENAI, ZAPI_PHONE_HEADER
from app.models.receive_message import WebhookMessage, WebhookProcessor
from app.models.history_service import HistoricoConversas
from app.models.search_chunks import BuscadorChunks
from app.models.openai_service import ChatInput, ChatResponder
from app.models.send_message import MensagemDispatcher
from app.models.config_info import ConfigService
from app.models.funnel_service import FunnelService
from app.services.pipeline_functions import fetch_funnel_info, fetch_user_info, calculate_user_info
from app.utils.logger import logger

openai.api_key = API_KEY_OPENAI
zapi_phone_header = ZAPI_PHONE_HEADER

async def process_message(body: dict) -> dict:
    start_time = time.monotonic()

    # Recebe a cria objeto com informações do webhook.
    webhook = WebhookMessage(**body)

    # Objeto com métodos e atributos do histórico de conversas.
    historico = HistoricoConversas(webhook.connectedPhone, webhook.phone)
    await historico.carregar()

    # Objeto com métodos e atributos das configurações dos nossos cliente.
    config_info = ConfigService(webhook.connectedPhone)
    await config_info.get()

    # Tratamento da mensagem (Audio e Debouncer)
    webhook_process = WebhookProcessor(webhook, config_info.tempo_espera_debounce)
    await webhook_process.processar()

    # Só processa se a mensagem não for do próprio bot/assistente
    if not webhook.fromMe:
        chunks = BuscadorChunks(config_info.pinecone_index_name, config_info.pinecone_namespace)
        await chunks.buscar(webhook_process.mensagem_consolidada)

        #funnel_info = await fetch_funnel_info(webhook.connectedPhone)
        funnel_info = FunnelService(webhook.connectedPhone)
        await funnel_info.get()

        user_info = await fetch_user_info(webhook.connectedPhone, webhook.phone, funnel_info.funnel_info)
        updated_user_info, updated_prompt = await calculate_user_info(webhook_process.mensagem_consolidada, user_info, funnel_info.funnel_info, webhook.connectedPhone, webhook.phone)

        chat_input = ChatInput(
        mensagem=webhook_process.mensagem_consolidada,
        best_chunks=chunks.best_chunks,
        historico=historico.mensagens,
        prompt_base=funnel_info.prompt_base,
        prompt_state=updated_prompt,
        user_data=updated_user_info
    )
        responder = ChatResponder(chat_input)
        await responder.generate()

        prepara_envio = MensagemDispatcher(webhook.phone, responder.resposta, config_info.zapi_instance_id, config_info.zapi_token, zapi_phone_header)
        logger.info(f"OBJETO MENSAGEM DISPATCHER:\n numero: {prepara_envio.numero}\n segmentos: {prepara_envio.segmentos}\n url: {prepara_envio.url}\n headers: {prepara_envio.headers}\n retries: {prepara_envio.retries}\n delay_typing: {prepara_envio.delay_typing}\n delay_between: {prepara_envio.delay_between}\n timeout: {prepara_envio.timeout}\n client: {prepara_envio.client}")
        await prepara_envio.enviar_resposta()

        historico.adicionar_interacao("user", webhook_process.mensagem_consolidada)
        await historico.salvar()

    elif webhook.fromMe:
        historico.adicionar_interacao("system", webhook_process.mensagem_consolidada)
        await historico.salvar()
        
    else:
        logger.info(f"[🔕 IGNORADO] Mensagem do próprio bot/assistente: {webhook.phone} - {webhook.connectedPhone}")
        #funnel_result = await process_user_funnel(conversation['mensagem'], conversation['numero'], conversation['telefone_empresa'], conversation['nome_cliente'])
        #logger.info(f"[🚀 CONFIG_INFO ]\n {config_info} \n[🚀 CONFIG_INFO ]")
        #logger.info(f"[🚀 WEBHOOK_INFO ]\n {webhook_info} \n[🚀 WEBHOOK_INFO ]")
        #logger.info(f"[🚀 FUNNEL INFO ]\n {funnel_info} \n[🚀 FUNNEL INFO ]")
        #logger.info(f"[🚀 USER INFO ]\n {user_info} \n[🚀 USER INFO ]")
        #logger.info(f"[🚀 UPDATED USER INFO ]\n {updated_user_info} \n[🚀 UPDATED USER INFO ]")
        #logger.info(f"[🚀 UPDATED PROMPT ]\n {updated_prompt} \n[🚀 UPDATED PROMPT ]")
        #logger.info(f"[🚀 HISTORY_INFO ]\n {historico.mensagens} \n[🚀 HISTORY_INFO ]")
        #logger.info(f"[🚀 BEST_CHUNKS ]\n {chunks.best_chunks} \n[🚀 BEST_CHUNKS ]")
        #logger.info(f"[🚀 RESPOSTA ]\n {responder.resposta} \n[🚀 RESPOSTA ]")
        #logger.info(f"[🚀🚀✅ ENVIADO ✅🚀🚀]")
    
    elapsed = time.monotonic() - start_time
    logger.info(f"[⏱️ Tempo de execução total, BOT*{webhook.fromMe}*]: {elapsed:.3f} segundos")


