# utils/message_aggregator.py
import asyncio
from collections import defaultdict
from app.utils.logger import logger

DEBOUNCE_DELAY = 5
_message_buffers = defaultdict(list)
_message_tasks = {}

async def debounce_and_collect(phone: str, empresa: str, mensagem: str) -> str:
    key = f"{phone}:{empresa}"
    _message_buffers[key].append(mensagem)

    if key in _message_tasks:
        _message_tasks[key].cancel()

    future = asyncio.get_event_loop().create_future()

    async def finalize():
        try:
            await asyncio.sleep(DEBOUNCE_DELAY)
            mensagens = _message_buffers.pop(key, [])
            texto_agrupado = " ".join(mensagens).strip()
            future.set_result(texto_agrupado)
        except asyncio.CancelledError:
            logger.debug(f"[🔁 REINICIANDO DEBOUNCE] {key}")
        finally:
            _message_tasks.pop(key, None)

    _message_tasks[key] = asyncio.create_task(finalize())
    return await future
