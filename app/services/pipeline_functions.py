import json
import re
from typing import Tuple
from app.config.redis_client import redis_client
from app.config.supabase_client import supabase
from app.models.receive_message import WebhookMessage, ConfigInfo, FunnelInfo, UserInfo
from app.services.openai_service import extract_message_content
from app.utils.logger import logger
from app.utils.message_aggregator import debounce_and_collect

async def fetch_config_info(telefone_cliente: str) -> ConfigInfo:
    SUPABASE_ACCOUNT_DATA = "account_data"
    CONFIG_INFO = "config_info"
    CACHE_TTL_SECONDS = None  # Sem TTL para dados estáticos de configuração
    
    cache_key = f"{CONFIG_INFO}:{telefone_cliente}"

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
            .eq("telefone_cliente", telefone_cliente)\
            .order("id", desc=True)\
            .limit(1)\
            .single()\
            .execute()

        if res.data:
            config_info = res.data.get(CONFIG_INFO)
            if not config_info:
                logger.error(f"[fetch_config_info] Campo '{CONFIG_INFO}' ausente no Supabase para telefone: {telefone_cliente}")
                raise RuntimeError(f"Erro crítico: Campo '{CONFIG_INFO}' ausente para telefone_cliente {telefone_cliente}")

            await redis_client.set(cache_key, json.dumps(config_info), ex=CACHE_TTL_SECONDS)
            return ConfigInfo.from_dict(config_info)

        logger.error(f"[fetch_config_info] Nenhum dado encontrado no Supabase para telefone_cliente: {telefone_cliente}")
    except Exception as e:
        logger.exception(f"[fetch_config_info] Erro ao consultar Supabase: {e}")

    raise RuntimeError(f"Erro crítico: Falha ao carregar config_info para telefone_cliente {telefone_cliente}")


async def fetch_funnel_info(telefone_cliente: str) -> FunnelInfo:
    SUPABASE_ACCOUNT_DATA = "account_data"
    FUNNEL_INFO = "funnel_info"
    CACHE_TTL_SECONDS = None
    
    cache_key = f"{FUNNEL_INFO}:{telefone_cliente}"

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
            .eq("telefone_cliente", telefone_cliente)\
            .order("id", desc=True)\
            .limit(1)\
            .single()\
            .execute()

        if res.data:
            funnel_info = res.data.get(FUNNEL_INFO)
            if not funnel_info:
                logger.error(f"[fetch_funnel_info] Campo '{FUNNEL_INFO}' ausente no Supabase para telefone: {telefone_cliente}")
                raise RuntimeError(f"Erro crítico: Campo '{FUNNEL_INFO}' ausente para telefone_cliente {telefone_cliente}")

            await redis_client.set(cache_key, json.dumps(funnel_info), ex=CACHE_TTL_SECONDS)
            return FunnelInfo.from_dict(funnel_info)

        logger.error(f"[fetch_funnel_info] Nenhum dado encontrado no Supabase para telefone_cliente: {telefone_cliente}")
    except Exception as e:
        logger.exception(f"[fetch_funnel_info] Erro ao consultar Supabase: {e}")

    raise RuntimeError(f"Erro crítico: Falha ao carregar funnel_info para telefone_cliente {telefone_cliente}")

async def webhook_treatment(webhook: WebhookMessage, tempo_espera_debounce: int) -> WebhookMessage:
    mensagem = await extract_message_content(webhook)

    if not mensagem:
        logger.info(f"[🔕 IGNORADO] Mensagem vazia | {webhook.phone}")
        webhook.mensagem = ""
        return webhook

    if tempo_espera_debounce > 0:
        mensagem = await debounce_and_collect(
            webhook.phone, webhook.connectedPhone, mensagem, tempo_espera_debounce
        )

    webhook.agrupar_mensagem(mensagem)
    return webhook


async def fetch_user_info(telefone_cliente: str, telefone_usuario: str, funnel_info: FunnelInfo) -> UserInfo:
    """Busca o user_info do Redis ou Supabase, com fallback automático"""
    SUPABASE_USER_INFO_TABLE = "user_data"
    USER_INFO = "user_info"
    CACHE_TTL_SECONDS = 14400  # 4h

    cache_key = f"{USER_INFO}:{telefone_cliente}:{telefone_usuario}"

    # 1. Tenta buscar no Redis
    cached_data = await redis_client.get(cache_key)
    if cached_data:
        try:
            return UserInfo.from_dict(json.loads(cached_data))
        except json.JSONDecodeError:
            logger.warning(f"[fetch_user_info] JSON inválido no cache Redis: {cache_key}")
            await redis_client.delete(cache_key)

    # 2. Busca no Supabase
    try:
        res = supabase.table(SUPABASE_USER_INFO_TABLE)\
            .select(USER_INFO)\
            .eq("telefone_cliente", telefone_cliente)\
            .eq("telefone_usuario", telefone_usuario)\
            .order("id", desc=True)\
            .limit(1)\
            .execute()

        if res.data:
            user_info_raw = res.data[0].get(USER_INFO)
            if user_info_raw:
                user_info_obj = UserInfo.from_dict(user_info_raw)
                user_info_obj = sync_user_info_with_funnel(user_info_obj, funnel_info)

                await redis_client.set(cache_key, json.dumps(user_info_obj.to_dict()), ex=CACHE_TTL_SECONDS)
                return user_info_obj

    except Exception as e:
        logger.exception(f"[fetch_user_info] Erro ao consultar Supabase: {e}")

    # 3. Fallback: criar novo registro se nenhum for encontrado ou erro
    logger.info(f"[fetch_user_info] Criando novo user_info para {telefone_usuario}")
    return await create_initial_user_info(telefone_cliente, telefone_usuario, funnel_info)

async def create_initial_user_info(telefone_cliente: str, telefone_usuario: str, funnel_info: FunnelInfo) -> UserInfo:
    SUPABASE_USER_INFO_TABLE = "user_data"
    USER_INFO = "user_info"
    CACHE_TTL_SECONDS = 14400

    # Pega o primeiro estado do funil
    initial_state = funnel_info.funil[0].id if funnel_info.funil else ""
    tracking_dict = funnel_info.to_tracking_dict(estado_atual=initial_state)
    initial_info = UserInfo(**tracking_dict)

    payload = {
        "telefone_cliente": telefone_cliente,
        "telefone_usuario": telefone_usuario,
        "user_info": initial_info.to_dict()
    } # Isso vai ser usado para criar o registro no Supabase, depois será implementado

    try:
        # Atualiza Redis
        await redis_client.set(
            f"{USER_INFO}:{telefone_cliente}:{telefone_usuario}",
            json.dumps(initial_info.to_dict()),
            ex=CACHE_TTL_SECONDS
        )

        logger.info(f"[create_initial_user_info] Registro criado ou atualizado para {telefone_usuario}")
        return initial_info

    except Exception as e:
        logger.exception(f"[create_initial_user_info] Erro ao criar/atualizar user_info: {e}")
        raise RuntimeError("Erro ao criar ou atualizar o estado inicial do usuário")

def sync_user_info_with_funnel(user_info: UserInfo, funnel_info: FunnelInfo) -> UserInfo:
    funnel_ids = [etapa.id for etapa in funnel_info.funil]

    updated_data = {
        etapa_id: user_info.data.get(etapa_id, None)
        for etapa_id in funnel_ids
    }

    updated_state = user_info.state if user_info.state in funnel_ids else funnel_ids[0] if funnel_ids else ""

    return UserInfo(state=updated_state, data=updated_data)

import json

async def calculate_user_info(mensagem: str, user_info: UserInfo, funnel_info: FunnelInfo, telefone_cliente: str, telefone_usuario: str) -> Tuple[UserInfo, str]:
    """
    Atualiza múltiplos campos do user_info com base em uma única mensagem.
    - Primeiro percorre todo o funil para tentar extrair todos os dados possíveis.
    - Só retorna prompt do primeiro estado ainda pendente após essa atualização.
    - Se um campo for obrigatório e ainda não preenchido, retorna o prompt dele.
    - Se não for obrigatório e não foi extraído, envia prompt uma vez antes de marcar como 'Nao informado'.
    """
    CACHE_TTL_SECONDS = 14400
    mensagem_lower = mensagem.lower()
    primeiro_prompt = None
    original_info = user_info.to_dict()  # Para checar alterações

    for etapa in funnel_info.funil:
        estado_id = etapa.id
        valor_atual = user_info.data.get(estado_id)
        pode_validar = valor_atual is None or etapa.permite_nova_entrada

        if not pode_validar:
            continue

        valor_extraido = None

        # REGEX
        if etapa.regex:
            for pattern in etapa.regex:
                match = re.search(pattern, mensagem_lower)
                if match:
                    grupos = match.groupdict()
                    valor_extraido = list(grupos.values())[0]
                    break

        # ALIASES
        if not valor_extraido and etapa.aliases:
            for chave, regras in etapa.aliases.items():
                frases = regras.get("frases") or []
                palavras = regras.get("palavras") or []

                if any(frase.lower() in mensagem_lower for frase in frases):
                    valor_extraido = chave
                    break

                if any(palavra.lower() in mensagem_lower.split() for palavra in palavras):
                    valor_extraido = chave
                    break

        # Atualização de valor
        if valor_extraido:
            user_info.data[estado_id] = valor_extraido

        elif valor_atual is None:
            if etapa.obrigatorio:
                if not primeiro_prompt:
                    primeiro_prompt = (estado_id, etapa.prompt)
            else:
                if user_info.state != estado_id:
                    if not primeiro_prompt:
                        primeiro_prompt = (estado_id, etapa.prompt)
                else:
                    user_info.data[estado_id] = "Nao informado"

    # Salvar se houver mudança
    updated_info = user_info.to_dict()
    if updated_info != original_info:
        cache_key = f"user_info:{telefone_cliente}:{telefone_usuario}"
        await redis_client.set(cache_key, json.dumps(updated_info), ex=CACHE_TTL_SECONDS)
        logger.info(f"[calculate_user_info] Dados atualizados no Redis para {telefone_usuario}")

    # Próximo estado pendente
    if primeiro_prompt:
        estado_id, prompt = primeiro_prompt
        user_info.state = estado_id
        return user_info, prompt

    # Finalizado
    user_info.state = "esperando_humano"
    etapa_final = next((e for e in funnel_info.funil if e.id == "esperando_humano"), None)
    return user_info, etapa_final.prompt if etapa_final else "Muito obrigado! Em breve a Jaqueline irá te atender por aqui."


async def save_user_info_if_changed(telefone_cliente: str, telefone_usuario: str, old_info: UserInfo, new_info: UserInfo, ttl_seconds: int = 14400):
    """Atualiza o Redis somente se o user_info tiver sido alterado"""
    old_json = json.dumps(old_info.to_dict(), sort_keys=True)
    new_json = json.dumps(new_info.to_dict(), sort_keys=True)

    if old_json != new_json:
        cache_key = f"user_info:{telefone_cliente}:{telefone_usuario}"
        await redis_client.set(cache_key, new_json, ex=ttl_seconds)
        logger.info(f"[save_user_info_if_changed] Atualizado user_info para {telefone_usuario}")
    else:
        logger.debug(f"[save_user_info_if_changed] Nenhuma alteração detectada para {telefone_usuario}")
