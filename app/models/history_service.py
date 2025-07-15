import json
import logging
from typing import Any, Dict, List, TypedDict

from aioredis import Redis
from app.config.redis_client import redis_client

logger = logging.getLogger(__name__)


class HistoryItem(TypedDict):
    role: str
    content: str


class RawHistoryService:
    """
    Grava *todos* os fragmentos na ordem que chegam,
    sem debounce, para uso em frontend tipo WhatsApp.
    """
    _KEY_TPL = "raw_history:{cliente}:{usuario}"
    _MAX_RAW_ENTRIES = 1000  # para não crescer sem controle

    def __init__(self, redis_client: Redis = redis_client):
        self.redis = redis_client

    def _key(self, cliente: str, usuario: str) -> str:
        return self._KEY_TPL.format(cliente=cliente, usuario=usuario)

    async def record(self, cliente: str, usuario: str, role: str, content: str) -> None:
        key = self._key(cliente, usuario)
        entry = json.dumps({"role": role, "content": content})
        try:
            await self.redis.rpush(key, entry)
            # manter só últimos N
            await self.redis.ltrim(key, -self._MAX_RAW_ENTRIES, -1)
        except Exception as err:
            logger.error("[RawHistoryService.record] erro em %s: %s", key, err)

    async def fetch_all(self, cliente: str, usuario: str) -> List[HistoryItem]:
        key = self._key(cliente, usuario)
        try:
            raws = await self.redis.lrange(key, 0, -1)
            return [json.loads(r) for r in raws]
        except Exception as err:
            logger.error("[RawHistoryService.fetch_all] erro em %s: %s", key, err)
            return []


class ChatHistoryService:
    """
    History “limpo” para montar prompt: só turnos de user/assistant.
    """
    _KEY_TPL = "chat_history:{cliente}:{usuario}"
    _TTL_SECONDS = 4 * 60 * 60    # 4h
    _MAX_ENTRIES = 6
    _SYSTEM_PROMPT: HistoryItem = {
        "role": "system",
        "content": "O cliente não tem histórico de interações com a empresa."
    }

    def __init__(self, redis_client: Redis = redis_client):
        self.redis = redis_client

    def _key(self, cliente: str, usuario: str) -> str:
        return self._KEY_TPL.format(cliente=cliente, usuario=usuario)

    async def fetch(self, cliente: str, usuario: str) -> List[HistoryItem]:
        key = self._key(cliente, usuario)
        try:
            raw = await self.redis.get(key)
            if raw:
                data = json.loads(raw)
                if isinstance(data, list):
                    return data
                logger.warning("[ChatHistoryService.fetch] inválido em %s: %s", key, type(data))
                await self.redis.delete(key)
        except Exception as err:
            logger.error("[ChatHistoryService.fetch] erro em %s: %s", key, err)
        return []

    async def save(self, cliente: str, usuario: str, history: List[HistoryItem]) -> None:
        key = self._key(cliente, usuario)
        payload = json.dumps(history)
        try:
            await self.redis.set(key, payload, ex=self._TTL_SECONDS)
        except Exception as err:
            logger.error("[ChatHistoryService.save] erro em %s: %s", key, err)

    async def add_message(self, cliente: str, usuario: str, mensagem: str, from_me: bool) -> List[HistoryItem]:
        """
        - busca histórico
        - inicializa com SYSTEM se vazio
        - adiciona USER ou ASSISTANT
        - trunca & persiste
        - retorna histórico atualizado
        """
        history = await self.fetch(cliente, usuario)
        if not history:
            history = [self._SYSTEM_PROMPT.copy()]

        role = "assistant" if from_me else "user"
        history.append({"role": role, "content": mensagem})
        history = history[-self._MAX_ENTRIES :]

        await self.save(cliente, usuario, history)
        return history
