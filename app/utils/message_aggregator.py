import asyncio
import aioredis
import os
from datetime import datetime

STREAM_KEY = "messages:{empresa}:{phone}"
GROUP   = "batchers"

async def worker(empresa: str, phone: str, debounce_ms: int = 10000):
    redis = await aioredis.create_redis_pool(os.environ.get("REDIS_URL"))
    key = STREAM_KEY.format(empresa=empresa, phone=phone)
    # Cria grupo se não existir
    try:
        await redis.xgroup_create(key, GROUP, id="0", mkstream=True)
    except aioredis.errors.ReplyError:
        pass  # Já existe

    buffer = []
    last_read_id = ">"
    while True:
        entries = await redis.xread_group(
            GROUP, f"consumer-{phone}", streams={key: last_read_id},
            count=100, latest_ids=None, timeout=debounce_ms
        )
        if not entries:
            # Timeout: agrupa o batch atual
            if buffer:
                await process_batch(buffer)
                buffer.clear()
            continue

        # Recebeu novos eventos
        for _, msgs in entries:
            for msg_id, fields in msgs:
                buffer.append(fields[b"mensagem"].decode())
                last_read_id = msg_id
        # Se explodir em tamanho, processa de imediato
        if len(buffer) >= 50:
            await process_batch(buffer)
            buffer.clear()
        # ACK todos até last_read_id
        await redis.xack(key, GROUP, last_read_id)

async def process_batch(batch):
    texto = ", ".join(batch)
    # ... processa como se fosse uma única mensagem
    print(f"[{datetime.utcnow()}] Processando: {texto[:50]}...")
