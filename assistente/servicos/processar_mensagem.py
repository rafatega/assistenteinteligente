import asyncio
from fastapi.concurrency import run_in_threadpool
from collections import defaultdict

# Buffers e controle de versão das tarefas
message_buffers = defaultdict(list)
task_versions = {}

# Delay configurável
DEBOUNCE_DELAY = 13  # segundos antes era 14

async def processa_mensagem(body: dict) -> dict:
    # Extrai conteúdo e metadados
    msg = await extract_message_content(body)
    numero = body.get("phone")
    telefone_empresa = body.get("connectedPhone")
    nome_cliente = body.get("senderName")