import json
import re
from typing import Tuple, Any, Dict, List
import copy
from app.config.redis_client import redis_client
from app.config.supabase_client import supabase
from app.models.receive_message import WebhookMessage, ConfigInfo, FunnelInfo, UserInfo
from app.services.openai_service import extract_message_content
from app.utils.logger import logger
from app.utils.message_aggregator import debounce_and_collect
from app.models.history_service import HistoryService

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

def sync_user_info_with_funnel(user_info: UserInfo, funnel_info: FunnelInfo) -> UserInfo:
    funnel_ids = [etapa.id for etapa in funnel_info.funil]

    updated_data = {
        etapa_id: user_info.data.get(etapa_id, None)
        for etapa_id in funnel_ids
    }

    updated_state = user_info.state if user_info.state in funnel_ids else funnel_ids[0] if funnel_ids else ""

    return UserInfo(state=updated_state, data=updated_data)

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


"""async def fetch_history_info(telefone_cliente: str, telefone_usuario: str) -> List[Dict[str, Any]]:
    """"""
    Busca o histórico de conversas no Redis para o par (telefone_cliente, telefone_usuario).
    Em caso de falha de acesso ou valor ausente/corrompido, retorna apenas o prompt sistêmico inicial.
    """"""
    HISTORY_KEY_TEMPLATE = "history:{telefone_cliente}:{telefone_usuario}"
    DEFAULT_HISTORY: Dict[str, str] = {
    "role": "system",
    "content": "O cliente não tem histórico de interações com a empresa."
    }

    key = HISTORY_KEY_TEMPLATE.format(
        telefone_cliente=telefone_cliente,
        telefone_usuario=telefone_usuario,
    )

    try:
        raw = await redis_client.get(key)
        if raw:
            history = json.loads(raw)
            if isinstance(history, list):
                return history
            # Dado inesperado no cache: log e limpeza
            logger.warning(
                "[fetch_history_info] Valor inválido no Redis para '%s': tipo %s",
                key, type(history).__name__
            )
            await redis_client.delete(key)
    except Exception as err:
        logger.error(
            "[fetch_history_info] Falha ao acessar Redis para chave '%s': %s",
            key, err
        )

    # Se não encontrou nada ou houve erro/corrupção, retorna o prompt inicial
    return [DEFAULT_HISTORY.copy()]

async def save_history_info(telefone_cliente: str, telefone_usuario: str, mensagem: str, from_me: bool, history) -> None:
    # Constantes de cache
    HISTORY_KEY_TEMPLATE = "history:{telefone_cliente}:{telefone_usuario}"
    HISTORY_TTL_SECONDS = 14400  # 4 horas
    MAX_HISTORY_ENTRIES = 6
    """"""
    Carrega o histórico, adiciona a mensagem como 'user' ou 'assistant',
    trunca para as últimas N entradas e salva de volta no Redis com TTL.
    """"""
    key = HISTORY_KEY_TEMPLATE.format(
        telefone_cliente=telefone_cliente,
        telefone_usuario=telefone_usuario,
    )

    # 1. Busca histórico atual (pode retornar lista vazia)
    history = await fetch_history_info(redis_client, telefone_cliente, telefone_usuario)

    # 2. Determina o role e adiciona a nova entrada
    role = "assistant" if from_me else "user"
    history.append({"role": role, "content": mensagem})

    # 3. Trunca para as últimas entradas
    truncated = history[-MAX_HISTORY_ENTRIES :]

    # 4. Persiste no Redis com TTL
    try:
        await redis_client.set(
            key,
            json.dumps(truncated),
            ex=HISTORY_TTL_SECONDS
        )
    except Exception as err:
        logger.error(
            "[save_history_info] Não foi possível salvar histórico para '%s': %s",
            key, err
        )
        # Se for um erro crítico, você pode re-raise ou alertar aqui."""