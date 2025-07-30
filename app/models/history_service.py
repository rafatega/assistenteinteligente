import json
import asyncio
from typing import Any
from datetime import datetime
from app.utils.logger import logger
from app.config.redis_client import redis_client
from app.config.supabase_client import supabase

class HistoricoConversas:
    TABLE = "user_data"
    FIELD = "history"
                                                                                                                                                                #14400
    def __init__(self, telefone_cliente: str, telefone_usuario: str, redis_client: Any = redis_client, tentativas: int = 3, mensagens: list = [], cache_ttl_seconds: int = 180):
        self.telefone_cliente = telefone_cliente
        self.telefone_usuario = telefone_usuario
        self.redis = redis_client
        self.tentativas = tentativas
        self.mensagens = mensagens
        self.cache_ttl_seconds = cache_ttl_seconds
        self.key = f"{self.FIELD}:{telefone_cliente}:{telefone_usuario}"
        self.primeiro_contato: bool = False

    async def carregar(self):
        for tentativa in range(self.tentativas):
            try:
                data = await self.redis.get(self.key)
                if data:
                    self.mensagens = json.loads(data)
                else:
                    await self._carregar_de_supabase()
                return
            except Exception as e:
                logger.error(f"[{self.key}] Erro Redis GET ({tentativa+1}): {e}")
                await asyncio.sleep(1)

        logger.critical(f"[{self.self.key}] Falha ao acessar Redis. Histórico mínimo carregado.")
        self.mensagens = [self._mensagem_inicial()]
    
    async def _carregar_de_supabase(self):
        try:
            id_cliente_usuario = f"{self.telefone_cliente}:{self.telefone_usuario}"
            res = supabase.table(self.TABLE)\
                .select(self.FIELD)\
                .eq("id_cliente_usuario", id_cliente_usuario)\
                .limit(1)\
                .execute()

            if res.data and res.data[0].get(self.FIELD):
                self.mensagens = res.data[0][self.FIELD]
                logger.info(f"[{self.key}] Histórico carregado via Supabase.")
                await self.redis.set(self.key, json.dumps(self.mensagens), ex=self.cache_ttl_seconds)
            else:
                logger.info(f"[{self.key}] Nenhum histórico encontrado no Supabase.")
                self.mensagens = [self._mensagem_inicial()]
        except Exception as e:
            logger.error(f"[{self.key}] Erro ao consultar Supabase: {e}")
            self.mensagens = [self._mensagem_inicial()]
    
    def _mensagem_inicial(self) -> dict:
        self.primeiro_contato = True
        return {
            "role": "system",
            "content": "O cliente não tem histórico de interações nos registros."
        }

    def adicionar_interacao(self, role: str, content: str):
        self.mensagens.append({
            "role": role,
            "content": content
        })

    async def salvar(self, max_mensagens: int = 8):
        mensagens_finais = self.mensagens[-max_mensagens:]

        # Tenta salvar no Redis
        for tentativa in range(self.tentativas):
            try:
                await self.redis.set(self.key, json.dumps(mensagens_finais), ex=self.cache_ttl_seconds)
                break
            except Exception as e:
                logger.error(f"[{self.key}] Erro Redis SET ({tentativa+1}): {e}")
                await asyncio.sleep(1)
        else:
            logger.critical(f"[{self.key}] Falha ao salvar histórico no Redis.")

        # Salva também no Supabase
        try:
            id_cliente_usuario = f"{self.telefone_cliente}:{self.telefone_usuario}"
            # Gerar updated_at no fuso de São Paulo, sem offset
            updated_at = datetime.now().astimezone().isoformat()

            supabase.table(self.TABLE).upsert({
                "id_cliente_usuario": id_cliente_usuario,
                "telefone_cliente": self.telefone_cliente,
                "telefone_usuario": self.telefone_usuario,
                "history": mensagens_finais,
                "updated_at": updated_at
            }, 
            on_conflict=["id_cliente_usuario"]
            ).execute()
        except Exception as e:
            logger.error(f"[{self.key}] Erro ao salvar histórico no Supabase: {e}")

