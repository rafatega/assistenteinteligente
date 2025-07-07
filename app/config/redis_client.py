import redis.asyncio as aioredis

from app.config.config import REDIS_URL

# Conecta ao Redis
redis_client = aioredis.from_url(
    REDIS_URL,
    encoding="utf-8",
    decode_responses=True,
    max_connections=20,
    socket_timeout=5,
    # a cada 30s o driver envia PING em conexões ociosas
    health_check_interval=30,
    # ativa TCP keep-alive para não derrubar por inatividade
    socket_keepalive=True
)