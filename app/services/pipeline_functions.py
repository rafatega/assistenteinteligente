import json
from app.config.redis_client import redis_client
from app.config.supabase_client import supabase
from app.models.receive_message import WebhookMessage, ConfiguracaoCliente
from app.services.openai_service import extract_message_content
from app.utils.logger import logger
from app.utils.message_aggregator import debounce_and_collect

async def fetch_account_data(telefone_empresa: str) -> ConfiguracaoCliente:
    ACCOUNT_DATA = "account_data"
    CACHE_TTL_SECONDS = 3600  # 1 hora
    
    cache_key = f"{ACCOUNT_DATA}:{telefone_empresa}"

    # 1. Tenta buscar no Redis
    cached_data = await redis_client.get(cache_key)
    if cached_data:
        try:
            return ConfiguracaoCliente.from_dict(json.loads(cached_data))
        except json.JSONDecodeError:
            logger.warning(f"[fetch_account_data] JSON inválido no cache Redis: {cache_key}")
            await redis_client.delete(cache_key)

    # 2. Busca no Supabase
    try:
        res = supabase.table(ACCOUNT_DATA).select("*").eq("telefone_empresa", telefone_empresa).limit(1).execute()
        if res.data and len(res.data) > 0:
            account_config = res.data[0]

            if "account_info" not in account_config:
                logger.warning(f"[fetch_account_data] Dados incompletos no Supabase: {account_config}")
                return build_default_account_config()

            await redis_client.set(cache_key, json.dumps(account_config), ex=CACHE_TTL_SECONDS)
            return ConfiguracaoCliente.from_dict(account_config)

        logger.warning(f"[fetch_account_data] Nenhum dado encontrado para {telefone_empresa}")
    except Exception as e:
        logger.exception(f"[fetch_account_data] Erro ao consultar Supabase: {e}")

    # 3. Fallback
    return build_default_account_config()


def build_default_account_config() -> ConfiguracaoCliente:
    return ConfiguracaoCliente(
        telefone_empresa="",
        prompt_base="Olá! Sou a assistente virtual Diana, recepcionista da Dra. Fluvia.",
        tempo_espera_debounce=5,
        funil=[]
    )

async def conversation_pipeline(webhook: WebhookMessage, tempo_espera_debounce: int) -> WebhookMessage:
    mensagem = await extract_message_content(webhook)

    if not mensagem:
        logger.info(f"[🔕 IGNORADO] Mensagem vazia | {webhook.phone}")
        webhook.mensagem = ""
        return webhook

    agrupado = await debounce_and_collect(
        webhook.phone, webhook.connectedPhone, mensagem, tempo_espera_debounce
    )

    webhook.agrupar_mensagem(agrupado)
    return webhook
