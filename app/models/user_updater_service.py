import json
import re
import copy
import openai
from datetime import datetime
from typing import Any, Tuple, Optional, Any
from app.config.redis_client import redis_client
from app.config.supabase_client import supabase
from app.utils.logger import logger
from app.models.user_info import UserInfo
from app.models.funnel_service import FunnelInfo
from app.models.openai_service import FallbackLLM


RETRY_ATTEMPTS = 2
CHAT_MODEL = "gpt-4"
FALLBACK_MODEL = "gpt-3.5-turbo"

class UserInfoUpdater:                                                                                                                          #14400
    def __init__(self, mensagem: str, user_info: UserInfo, funnel_info: FunnelInfo, telefone_cliente: str, telefone_usuario: str, historico: Any, cache_ttl: Optional[int] = 14400):
        self.mensagem = mensagem.lower()
        self.user_info = user_info
        self.funnel_info = funnel_info
        self.telefone_cliente = telefone_cliente
        self.telefone_usuario = telefone_usuario
        self.historico = historico
        self.cache_ttl = cache_ttl
        self.original_snapshot = copy.deepcopy(user_info.to_dict())
        self.first_prompt: Optional[Tuple[str, str]] = None
        self.response_prompt: Optional[str] = None

    async def process(self) -> None:
        await self._processar_funil()
        self._atualizar_estado()
        await self._salvar_se_necessario()
        self.response_prompt = self._get_response_prompt()

    async def change_state(self) -> None:
        self.user_info.state = "atendimento_humano"
        await self._salvar_se_necessario()

    async def _processar_funil(self) -> None:
        for etapa in self.funnel_info.funil:
            await self._processar_etapa(etapa)

    async def _processar_etapa(self, etapa: Any) -> None:
        estado_id = etapa.id
        valor_atual = self.user_info.data.get(estado_id)
        pode_validar = (valor_atual is None) or etapa.permite_nova_entrada

        if not pode_validar:
            return
        valor_extraido = await self._extrair_valor(etapa)
        if valor_extraido is not None:
            self.user_info.data[estado_id] = valor_extraido
        else:
            self._definir_prompt_para_etapa(etapa, valor_atual)

    async def _extrair_valor(self, etapa: Any) -> Optional[str]:
        fallback_prompt = getattr(etapa, "fallback_llm", None)
        if fallback_prompt:
            objeto_fallback = FallbackLLM(self.mensagem, fallback_prompt, self.historico)
            resposta_llm = await objeto_fallback.generate_fallback_llm()
            #logger.info(f"Perguntando para o Fallback LLM. Etapa: {etapa.id}")
            if resposta_llm:
                resposta = resposta_llm.strip().lower()
                #logger.info(f"Dado registrado pelo Fallback LLM. Etapa: {etapa.id}")
                return resposta
            return None
        return None
                
    def _definir_prompt_para_etapa(self, etapa: Any, valor_atual: Any) -> None:
        if not self.first_prompt:
            #if etapa.obrigatorio or valor_atual is None or self.user_info.state != etapa.id:
            if (etapa.obrigatorio and valor_atual is None and self.user_info.state != etapa.id) or (valor_atual is None and self.user_info.state != etapa.id):
                self.first_prompt = (etapa.id, etapa.prompt)
            elif not etapa.obrigatorio and self.user_info.state == etapa.id:
                self.user_info.data[etapa.id] = "nao_informado"

    def _atualizar_estado(self) -> None:
        if self.user_info.state == "atendimento_humano":
            return
        if self.first_prompt:
            self.user_info.state = self.first_prompt[0]
        else:
            self.user_info.state = "esperando_humano"

    async def _salvar_se_necessario(self) -> None:
        # Cache Redis
        # Muda estado caso seja paciente antigo ou outros assuntos;
        if self.user_info.data.get('tipo_cliente') in ('paciente_existente', 'outros_assuntos', 'nao_informado'):
            self.user_info.state = "atendimento_humano"
        current = self.user_info.to_dict()
        if current != self.original_snapshot:
            key = f"user_info:{self.telefone_cliente}:{self.telefone_usuario}"
            await redis_client.set(key, json.dumps(current), ex=self.cache_ttl)
            #logger.info(f"[UserInfoUpdater] Redis atualizado para {self.telefone_usuario}")

            # Supabase
            try:
                id_cliente_usuario = f"{self.telefone_cliente}:{self.telefone_usuario}"
                # Gerar updated_at no fuso de São Paulo, sem offset
                updated_at = datetime.now().astimezone().isoformat()

                supabase.table("user_data").upsert({
                    "id_cliente_usuario": id_cliente_usuario,
                    "telefone_cliente": self.telefone_cliente,
                    "telefone_usuario": self.telefone_usuario,
                    "user_info": json.dumps(current),
                    "updated_at": updated_at
                },
                on_conflict=["id_cliente_usuario"]
                ).execute()
            except Exception as e:
                logger.error(f"[update_user_funnel] Supabase error: {e}")

    def _get_response_prompt(self) -> str:
        if self.first_prompt:
            return self.first_prompt[1]

        etapa_final = next((e for e in self.funnel_info.funil if e.id == "esperando_humano"), None)
        return etapa_final.prompt if etapa_final else "Muito obrigado! Em breve a responsável pelo atendimento irá te chamar por aqui."
    
    @staticmethod
    async def chamar_llm(prompt: str, mensagem: str) -> str:
        for attempt in range(RETRY_ATTEMPTS):
            try:
                response = await openai.ChatCompletion.acreate(
                    model = CHAT_MODEL if attempt < RETRY_ATTEMPTS - 1 else FALLBACK_MODEL,
                    messages=[
                        {"role": "system", "content": prompt},
                        {"role": "user", "content": mensagem}
                    ],
                    temperature=0,
                    max_tokens=10,
                )
                return response.choices[0].message['content'].strip()
            except Exception as e:
                logger.info(f"Erro na chamada LLM da intencao: {e}")
        return "erro_llm"

