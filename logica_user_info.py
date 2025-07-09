import re
from typing import Tuple

async def calculate_user_info(mensagem: str, user_info: UserInfo, funnel_info: FunnelInfo) -> Tuple[UserInfo, str]:
    """
    Atualiza múltiplos campos do user_info com base em uma única mensagem.
    - Primeiro percorre todo o funil para tentar extrair todos os dados possíveis.
    - Só retorna prompt do primeiro estado ainda pendente após essa atualização.
    - Se um campo for obrigatório e ainda não preenchido, retorna o prompt dele.
    - Se não for obrigatório e não foi extraído, envia prompt uma vez antes de marcar como 'Nao informado'.
    """
    mensagem_lower = mensagem.lower()
    primeiro_prompt = None  # Guardar o prompt do primeiro estado pendente

    for etapa in funnel_info.funil:
        estado_id = etapa.id
        valor_atual = user_info.data.get(estado_id)
        pode_validar = valor_atual is None or etapa.permite_nova_entrada

        # Ignora se não pode validar
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
            # Se ainda não preencheu, pode ser o primeiro a precisar de resposta
            if etapa.obrigatorio:
                if not primeiro_prompt:
                    primeiro_prompt = (estado_id, etapa.prompt)
            else:
                # Se não for obrigatório, mostra prompt uma vez antes de marcar como "Nao informado"
                if user_info.state != estado_id:
                    if not primeiro_prompt:
                        primeiro_prompt = (estado_id, etapa.prompt)
                else:
                    user_info.data[estado_id] = "Nao informado"

    # Definir o próximo estado pendente
    if primeiro_prompt:
        estado_id, prompt = primeiro_prompt
        user_info.state = estado_id
        return user_info, prompt

    # Tudo preenchido
    user_info.state = "esperando_humano"
    etapa_final = next((e for e in funnel_info.funil if e.id == "esperando_humano"), None)
    return user_info, etapa_final.prompt if etapa_final else "Muito obrigado! Em breve a Jaqueline irá te atender por aqui."
