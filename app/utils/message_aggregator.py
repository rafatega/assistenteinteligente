import asyncio
import os
from redis.asyncio import Redis
from datetime import datetime

from app.utils.logger import logger
from app.config.redis_client import redis_client

debounce_tasks = {}
debounce_futures = {}


def _get_redis_key(phone: str, connected_phone: str) -> str:
    return f"debounce:{phone}:{connected_phone}"


async def debounce_and_collect(phone: str, connected_phone: str, mensagem: str, tempo_espera_debounce: int) -> str:
    redis_key = _get_redis_key(phone, connected_phone)

    task_key = f"{phone}:{connected_phone}"

    # Armazena mensagem
    await redis_client.rpush(redis_key, mensagem)

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
        _espera_e_retorna(redis_key, task_key, future, tempo_espera_debounce)
    )

    # Aguarda resultado final
    resultado = await future
    return resultado


async def _espera_e_retorna(redis_key: str, task_key: str, future: asyncio.Future, tempo_espera_debounce: int):
    try:
        logger.info(f"[⏳ Esperando 5s] {task_key}")
        await asyncio.sleep(tempo_espera_debounce)
        logger.info(f"[✅ Tempo de espera concluído]: {tempo_espera_debounce} segundos")

        mensagens = await redis_client.lrange(redis_key, 0, -1)
        logger.info(f"[📦 Mensagens encontradas] {mensagens}")

        await redis_client.delete(redis_key)

        resultado = ", ".join(mensagens)
        if not future.done():
            future.set_result(resultado)
        else:
            logger.warning(f"[⚠️ Future já resolvida] {task_key}")

        debounce_tasks.pop(task_key, None)
        debounce_futures.pop(task_key, None)
        logger.info(f"[✅ Resultado final enviado] {resultado}")
    except asyncio.CancelledError:
        logger.info(f"[🚫 Debounce cancelado] {task_key}")
