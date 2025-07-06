import asyncio
from collections import defaultdict
from typing import Callable, Awaitable
from app.utils.logger import logger

DEBOUNCE_DELAY = 5  # segundos

# Armazena as tarefas e buffers por cliente+empresa
_message_buffers = defaultdict(list)
_debounce_tasks = {}

def debounce_by_user(func: Callable[[str, str, list], Awaitable[None]]) -> Callable[[str, str, str], None]:
    """
    Decorator debounce para agrupar mensagens de um mesmo cliente/empresa em um intervalo de tempo.
    """
    async def _debounce_task(key: str, phone: str, empresa: str):
        await asyncio.sleep(DEBOUNCE_DELAY)

        mensagens = _message_buffers.pop(key, [])
        logger.info(f"[✅ DEBOUNCE FINALIZADO] {key} com {len(mensagens)} mensagens")
        await func(phone, empresa, mensagens)

    def wrapper(phone: str, empresa: str, mensagem: str):
        key = f"{phone}:{empresa}"
        _message_buffers[key].append(mensagem)

        # Cancela a task anterior (se houver)
        if task := _debounce_tasks.get(key):
            task.cancel()

        logger.debug(f"[⏳ NOVA MENSAGEM] Adicionada ao buffer de {key}")
        _debounce_tasks[key] = asyncio.create_task(_debounce_task(key, phone, empresa))

    return wrapper
