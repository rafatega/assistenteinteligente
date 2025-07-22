import json
import re
import copy
from typing import Any, Tuple, Optional
from app.config.redis_client import redis_client
from app.utils.logger import logger
from app.models.user_info import UserInfo
from app.models.funnel_service import FunnelInfo

class UserInfoUpdater:
    def __init__(self, mensagem: str, user_info: UserInfo, funnel_info: FunnelInfo, telefone_cliente: str, telefone_usuario: str, cache_ttl: Optional[int] = 14400):
        self.mensagem = mensagem.lower()
        self.user_info = user_info
        self.funnel_info = funnel_info
        self.telefone_cliente = telefone_cliente
        self.telefone_usuario = telefone_usuario
        self.cache_ttl = cache_ttl

        self.original_snapshot = copy.deepcopy(user_info.to_dict())
        self.first_prompt: Optional[Tuple[str, str]] = None

        self.updated_user_info: Optional[UserInfo] = None
        self.response_prompt: Optional[str] = None

    async def process(self) -> None:
        self._processar_funil()
        self._atualizar_estado()
        await self._salvar_se_necessario()
        self.response_prompt = self._get_response_prompt()

    def _processar_funil(self) -> None:
        for etapa in self.funnel_info.funil:
            self._processar_etapa(etapa)

    def _processar_etapa(self, etapa: Any) -> None:
        estado_id = etapa.id
        valor_atual = self.user_info.data.get(estado_id)
        pode_validar = (valor_atual is None) or etapa.permite_nova_entrada

        if not pode_validar:
            return

        valor_extraido = self._extrair_valor(etapa)
        if valor_extraido is not None:
            self.user_info.data[estado_id] = valor_extraido
        else:
            self._definir_prompt_para_etapa(etapa, valor_atual)

    def _extrair_valor(self, etapa: Any) -> Optional[str]:

        # REGEX
        for pattern in etapa.regex or []:
            match = re.search(pattern, self.mensagem)
            if match:
                grupos = match.groupdict()
                return next(iter(grupos.values()), None)

        # HEURÍSTICA
        for chave, regras in (etapa.aliases or {}).items():
            if not isinstance(regras, dict):
                continue

            for frase in regras.get("frases") or []:
                if frase.lower() in self.mensagem:
                    return chave

            tokens = self.mensagem.split()
            for palavra in regras.get("palavras") or []:
                if palavra.lower() in tokens:
                    return chave
                
        return None

    def _definir_prompt_para_etapa(self, etapa: Any, valor_atual: Any) -> None:
        if not self.first_prompt:
            if etapa.obrigatorio or valor_atual is None or self.user_info.state != etapa.id:
                self.first_prompt = (etapa.id, etapa.prompt)
            elif not etapa.obrigatorio and self.user_info.state == etapa.id:
                self.user_info.data[etapa.id] = "Nao informado"

    def _atualizar_estado(self) -> None:
        if self.first_prompt:
            self.user_info.state = self.first_prompt[0]
        else:
            self.user_info.state = "esperando_humano"

    async def _salvar_se_necessario(self) -> None:
        current = self.user_info.to_dict()
        if current != self.original_snapshot:
            key = f"user_info:{self.telefone_cliente}:{self.telefone_usuario}"
            await redis_client.set(key, json.dumps(current), ex=self.cache_ttl)
            logger.info(f"[UserInfoUpdater] Redis atualizado para {self.telefone_usuario}")

    def _get_response_prompt(self) -> str:
        if self.first_prompt:
            return self.first_prompt[1]

        etapa_final = next((e for e in self.funnel_info.funil if e.id == "esperando_humano"), None)
        return etapa_final.prompt if etapa_final else "Muito obrigado! Em breve a Jaqueline irá te atender por aqui."

