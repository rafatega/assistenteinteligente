import asyncio
import os
from app.utils.logger import logger
from redis.asyncio import Redis
from datetime import datetime

REDIS_URL = os.environ.get("REDIS_URL")

debounce_tasks = {}
debounce_futures = {}

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

    task_key = f"{phone}:{connected_phone}"

    # Armazena mensagem
    await redis_client.rpush(redis_key, mensagem)
    await redis_client.expire(redis_key, 10)

    # Se já houver tarefa, cancela e remove
    if task_key in debounce_tasks:
        debounce_tasks[task_key].cancel()
        debounce_tasks.pop(task_key, None)

    if task_key in debounce_futures:
        debounce_futures.pop(task_key, None)

    # Cria future para aguardar resultado
    future = asyncio.get_event_loop().create_future()
    debounce_futures[task_key] = future

    # Agenda nova tarefa debounce
    debounce_tasks[task_key] = asyncio.create_task(
        _espera_e_retorna(redis_key, task_key, future)
    )

    # Aguarda resultado final
    resultado = await future
    return resultado


async def _espera_e_retorna(redis_key: str, task_key: str, future: asyncio.Future):
    try:
        logger.info(f"[⏳ Esperando 10s] {task_key}")
        await asyncio.sleep(10)

        redis_client = await get_redis()
        mensagens = await redis_client.lrange(redis_key, 0, -1)
        logger.info(f"[📦 Mensagens encontradas] {mensagens}")

        await redis_client.delete(redis_key)

        resultado = " ".join(mensagens)
        if not future.done():
            future.set_result(resultado)
        else:
            logger.warning(f"[⚠️ Future já resolvida] {task_key}")

        debounce_tasks.pop(task_key, None)
        debounce_futures.pop(task_key, None)
        logger.info(f"[✅ Resultado final enviado] {resultado}")
    except asyncio.CancelledError:
        logger.info(f"[🚫 Debounce cancelado] {task_key}")
