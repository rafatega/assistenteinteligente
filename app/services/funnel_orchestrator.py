import json
import asyncio
from enum import Enum
from typing import Optional, Dict, Any, TypedDict
from app.utils.logger import logger

from app.config.redis_client import redis
from app.config.supabase_client import supabase


ACCOUNT_DATA = "account_data"
CACHE_TTL_SECONDS = 14400  # 4 horas

async def fetch_account_data(telefone_empresa: str) -> Dict[str, Any]:
    cache_key = f"{ACCOUNT_DATA}:{telefone_empresa}"

    # 1. Tenta buscar no cache Redis
    cached_data = await redis.get(cache_key)
    if cached_data:
        try:
            return json.loads(cached_data)
        except json.JSONDecodeError:
            logger.warning(f"[fetch_account_data] JSON inválido no cache Redis: {cache_key}")
            await redis.delete(cache_key)

    # 2. Busca no Supabase
    try:
        res = supabase.table(ACCOUNT_DATA).select("*").eq("telefone_empresa", telefone_empresa).limit(1).execute()
        if res.data and len(res.data) > 0:
            account_config = res.data[0]

            # Valida estrutura mínima obrigatória
            if "prompt_base" not in account_config or "funil" not in account_config:
                logger.warning(f"[fetch_account_data] Dados incompletos no Supabase: {account_config}")
                return build_default_account_config()

            # 3. Cacheia no Redis
            await redis.set(cache_key, json.dumps(account_config), ex=CACHE_TTL_SECONDS)
            return account_config
        else:
            logger.warning(f"[fetch_account_data] Nenhum dado encontrado para {telefone_empresa}")
    except Exception as e:
        logger.exception(f"[fetch_account_data] Erro ao consultar Supabase: {e}")

    # 4. Fallback local (default)
    return build_default_account_config()


def build_default_account_config() -> Dict[str, Any]:
    return {
        "prompt_base": "Olá! Sou a assistente virtual Diana, recepcionista da Dra. Fluvia.",
        "funil": [],
        "tempo_espera_debounce": 5
    }


# -- Funnel Orchestration
async def process_user_funnel(mensagem: str, numero: str, telefone_empresa: str, nome_cliente: str) -> str:
    account_data = await fetch_account_data(telefone_empresa)
    #lead_data = await fetch_lead_data(numero, telefone_empresa)
    return 'Finalizado com sucesso'