import json
import asyncio
from enum import Enum
from typing import Optional, Dict, Any, TypedDict
from app.utils.logger import logger

from app.config.redis_client import redis_client
from app.config.supabase_client import supabase
from app.models.account_config import ConfiguracaoClinica


ACCOUNT_DATA = "account_data"
CACHE_TTL_SECONDS = 3600  # 1 hora

async def fetch_account_data(telefone_empresa: str) -> ConfiguracaoClinica:
    cache_key = f"{ACCOUNT_DATA}:{telefone_empresa}"

    # 1. Tenta buscar no Redis
    cached_data = await redis_client.get(cache_key)
    if cached_data:
        try:
            return ConfiguracaoClinica.from_dict(json.loads(cached_data))
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
            return ConfiguracaoClinica.from_dict(account_config)

        logger.warning(f"[fetch_account_data] Nenhum dado encontrado para {telefone_empresa}")
    except Exception as e:
        logger.exception(f"[fetch_account_data] Erro ao consultar Supabase: {e}")

    # 3. Fallback
    return build_default_account_config()


def build_default_account_config() -> ConfiguracaoClinica:
    return ConfiguracaoClinica(
        telefone_empresa="",
        prompt_base="Olá! Sou a assistente virtual Diana, recepcionista da Dra. Fluvia.",
        tempo_espera_debounce=5,
        funil=[]
    )



# -- Funnel Orchestration
async def process_user_funnel(mensagem: str, numero: str, telefone_empresa: str, nome_cliente: str) -> str:
    account_data = await fetch_account_data(telefone_empresa)
    logger.info(f"[🚀 FUNIL ORCHESTRATOR] Processando funil: {account_data}")
    #lead_data = await fetch_lead_data(numero, telefone_empresa)
    return 'Finalizado com sucesso'