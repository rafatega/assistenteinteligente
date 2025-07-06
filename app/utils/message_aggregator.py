import asyncio
import os
from redis.asyncio import Redis
from datetime import datetime

REDIS_URL = os.environ.get("REDIS_URL")

debounce_tasks = {}

redis: Redis = None

async def get_redis():
    global redis
    if not redis:
        redis = Redis.from_url(REDIS_URL, decode_responses=True)
    return redis


def _get_redis_key(phone: str, connected_phone: str) -> str:
    return f"debounce:{phone}:{connected_phone}"


async def debounce_and_collect(phone: str, connected_phone: str, mensagem: str) -> str:
    redis_key = _get_redis_key(phone, connected_phone)
    redis_client = await get_redis()

    # Armazena mensagem
    await redis_client.rpush(redis_key, mensagem)
    await redis_client.expire(redis_key, 10)  # Reinicia TTL para 10s

    # Cancela tarefa anterior se existir
    task_key = f"{phone}:{connected_phone}"
    if task_key in debounce_tasks:
        debounce_tasks[task_key].cancel()

    # Cria nova tarefa de agregacao
    debounce_tasks[task_key] = asyncio.create_task(
        _espera_e_retorna(redis_key, task_key)
    )

    # Retorna mensagens acumuladas até agora
    mensagens = await redis_client.lrange(redis_key, 0, -1)
    return " ".join(mensagens)


async def _espera_e_retorna(redis_key: str, task_key: str):
    try:
        await asyncio.sleep(10)
        redis_client = await get_redis()
        await redis_client.delete(redis_key)
        debounce_tasks.pop(task_key, None)
    except asyncio.CancelledError:
        pass
