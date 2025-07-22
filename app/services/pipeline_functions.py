import json
import re
from typing import Tuple
import copy
from app.config.redis_client import redis_client
from app.config.supabase_client import supabase
from app.models.receive_message import UserInfo
from app.utils.logger import logger

async def fetch_user_info(telefone_cliente: str, telefone_usuario: str, funnel_info) -> UserInfo:
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

async def create_initial_user_info(telefone_cliente: str, telefone_usuario: str, funnel_info) -> UserInfo:
    SUPABASE_USER_INFO_TABLE = "user_data"
    USER_INFO = "user_info"
    CACHE_TTL_SECONDS = 14400

    # Pega o primeiro estado do funil
    initial_state = None
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

def sync_user_info_with_funnel(user_info: UserInfo, funnel_info) -> UserInfo:
    funnel_ids = [etapa.id for etapa in funnel_info.funil]

    updated_data = {
        etapa_id: user_info.data.get(etapa_id, None)
        for etapa_id in funnel_ids
    }

    updated_state = user_info.state if user_info.state in funnel_ids else funnel_ids[0] if funnel_ids else ""

    return UserInfo(state=updated_state, data=updated_data)

async def calculate_user_info(mensagem: str, user_info: UserInfo, funnel_info, telefone_cliente: str, telefone_usuario: str) -> Tuple[UserInfo, str]:
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
    original_info = copy.deepcopy(user_info.to_dict())  # clone total antes

    for etapa in funnel_info.funil:
        estado_id = etapa.id
        valor_atual = user_info.data.get(estado_id)
        pode_validar = valor_atual is None or etapa.permite_nova_entrada

        if not pode_validar:
            continue

        valor_extraido = None

        if etapa.regex:
            for pattern in etapa.regex:
                match = re.search(pattern, mensagem_lower)
                if match:
                    grupos = match.groupdict()
                    valor_extraido = list(grupos.values())[0]
                    break

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

    # Ajuste de estado
    if primeiro_prompt:
        estado_id, prompt = primeiro_prompt
        user_info.state = estado_id
    else:
        user_info.state = "esperando_humano"

    # Comparação e atualização
    updated_info = user_info.to_dict()
    if updated_info != original_info:
        cache_key = f"user_info:{telefone_cliente}:{telefone_usuario}"
        await redis_client.set(cache_key, json.dumps(updated_info), ex=CACHE_TTL_SECONDS)
        logger.info(f"[calculate_user_info] Dados atualizados no Redis para {telefone_usuario}")

    # Resposta ao usuário
    if primeiro_prompt:
        return user_info, primeiro_prompt[1]

    etapa_final = next((e for e in funnel_info.funil if e.id == "esperando_humano"), None)
    return user_info, etapa_final.prompt if etapa_final else "Muito obrigado! Em breve a Jaqueline irá te atender por aqui."