import json
import re
from typing import Tuple
import copy
from app.config.redis_client import redis_client
from app.models.user_info import UserInfo
from app.utils.logger import logger

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