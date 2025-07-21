import json
import asyncio
from app.utils.logger import logger

class HistoricoConversas:
    PREFIX = "history:"

    def __init__(self, redis_client, telefone_cliente: str, telefone_usuario: str):
        self.redis = redis_client
        self.key = f"{self.PREFIX}{telefone_cliente}:{telefone_usuario}"
        self.tentativas = 3
        self.mensagens = []
        self.cache_ttl_seconds = 14400

    async def carregar(self):
        for tentativa in range(self.tentativas):
            try:
                data = await self.redis.get(self.key)
                if data:
                    self.mensagens = json.loads(data)
                else:
                    self.mensagens = [self._mensagem_inicial()]
                return
            except Exception as e:
                logger.error(f"[{self.key}] Erro Redis GET ({tentativa+1}): {e}")
                await asyncio.sleep(1)
        logger.critical(f"[{self.key}] Falha ao acessar Redis. Histórico mínimo carregado.")
        self.mensagens = [self._mensagem_inicial()]

    def adicionar_interacao(self, role: str, content: str):
        self.mensagens.append({
            "role": role,
            "content": content
        })

    async def salvar(self, max_mensagens: int = 8):
        mensagens_finais = self.mensagens[-max_mensagens:]
        for tentativa in range(self.tentativas):
            try:
                await self.redis.set(self.key, json.dumps(mensagens_finais), ex=self.cache_ttl_seconds)
                return
            except Exception as e:
                logger.error(f"[{self.key}] Erro Redis SET ({tentativa+1}): {e}")
                await asyncio.sleep(1)
        logger.critical(f"[{self.key}] Falha ao salvar histórico no Redis.")

    def _mensagem_inicial(self) -> dict:
        return {
            "role": "system",
            "content": "O cliente não tem histórico de interações com a empresa."
        }
