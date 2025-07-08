import json
from app.config.redis_client import redis_client
from app.config.supabase_client import supabase
from app.models.receive_message import WebhookMessage, ConfigInfo, FunnelInfo
from app.services.openai_service import extract_message_content
from app.utils.logger import logger
from app.utils.message_aggregator import debounce_and_collect

SUPABASE_ACCOUNT_DATA = "account_data"

async def fetch_config_info(telefone_empresa: str) -> ConfigInfo:
    CONFIG_INFO = "config_info"
    CACHE_TTL_SECONDS = None  # Sem TTL para dados estáticos de configuração
    
    cache_key = f"{CONFIG_INFO}:{telefone_empresa}"

    # 1. Tenta buscar no Redis
    cached_data = await redis_client.get(cache_key)
    if cached_data:
        try:
            return ConfigInfo.from_dict(json.loads(cached_data))
        except json.JSONDecodeError:
            logger.warning(f"[fetch_config_info] JSON inválido no cache Redis: {cache_key}")
            await redis_client.delete(cache_key)

    # 2. Busca no Supabase
    try:
        res = supabase.table(SUPABASE_ACCOUNT_DATA)\
            .select(CONFIG_INFO)\
            .eq("telefone_empresa", telefone_empresa)\
            .order("id", desc=True)\
            .limit(1)\
            .single()\
            .execute()

        if res.data:
            config_info = res.data.get(CONFIG_INFO)
            if not config_info:
                logger.error(f"[fetch_config_info] Campo '{CONFIG_INFO}' ausente no Supabase para telefone: {telefone_empresa}")
                raise RuntimeError(f"Erro crítico: Campo '{CONFIG_INFO}' ausente para telefone_empresa {telefone_empresa}")

            await redis_client.set(cache_key, json.dumps(config_info), ex=CACHE_TTL_SECONDS)
            return ConfigInfo.from_dict(config_info)

        logger.error(f"[fetch_config_info] Nenhum dado encontrado no Supabase para telefone_empresa: {telefone_empresa}")
    except Exception as e:
        logger.exception(f"[fetch_config_info] Erro ao consultar Supabase: {e}")

    raise RuntimeError(f"Erro crítico: Falha ao carregar config_info para telefone_empresa {telefone_empresa}")


async def fetch_funnel_info(telefone_empresa: str) -> FunnelInfo:
    FUNNEL_INFO = "funnel_info"
    CACHE_TTL_SECONDS = None
    
    cache_key = f"{FUNNEL_INFO}:{telefone_empresa}"

    # 1. Tenta buscar no Redis
    cached_data = await redis_client.get(cache_key)
    if cached_data:
        try:
            return FunnelInfo.from_dict(json.loads(cached_data))
        except json.JSONDecodeError:
            logger.warning(f"[fetch_funnel_info] JSON inválido no cache Redis: {cache_key}")
            await redis_client.delete(cache_key)

    # 2. Busca no Supabase
    try:
        res = supabase.table(SUPABASE_ACCOUNT_DATA)\
            .select(FUNNEL_INFO)\
            .eq("telefone_empresa", telefone_empresa)\
            .order("id", desc=True)\
            .limit(1)\
            .single()\
            .execute()

        if res.data:
            funnel_info = res.data.get(FUNNEL_INFO)
            if not funnel_info:
                logger.error(f"[fetch_funnel_info] Campo '{FUNNEL_INFO}' ausente no Supabase para telefone: {telefone_empresa}")
                raise RuntimeError(f"Erro crítico: Campo '{FUNNEL_INFO}' ausente para telefone_empresa {telefone_empresa}")

            await redis_client.set(cache_key, json.dumps(funnel_info), ex=CACHE_TTL_SECONDS)
            return FunnelInfo.from_dict(funnel_info)

        logger.error(f"[fetch_funnel_info] Nenhum dado encontrado no Supabase para telefone_empresa: {telefone_empresa}")
    except Exception as e:
        logger.exception(f"[fetch_funnel_info] Erro ao consultar Supabase: {e}")

    raise RuntimeError(f"Erro crítico: Falha ao carregar funnel_info para telefone_empresa {telefone_empresa}")



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
