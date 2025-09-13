from pydantic import BaseModel
import requests
import openai
import asyncio
from typing import Optional
from app.config.redis_client import redis_client
from app.utils.logger import logger

class WebhookMessage(BaseModel):
    connectedPhone: str
    isGroup: bool
    isEdit: bool
    phone: str
    fromMe: bool
    momment: int
    senderName: Optional[str] = None
    text: Optional[dict] = None
    audio: Optional[dict] = None

    @property
    def mensagem_texto(self) -> Optional[str]:
        if self.text:
            return self.text.get("message")
        return None

    @property
    def url_audio(self) -> Optional[str]:
        if self.audio:
            return self.audio.get("audioUrl")
        return None

debounce_tasks = {}
debounce_futures = {}
class WebhookProcessor:
    def __init__(self, webhook: WebhookMessage, debounce_timeout: int):
        self.webhook = webhook
        self.debounce_timeout = debounce_timeout
        self.debounce_timeout_assistant: int = 3
        self.mensagem_consolidada = ""

    async def processar(self) -> WebhookMessage:
        mensagem = await self.extrair_mensagem()

        if not mensagem:
            #logger.info(f"[🔕 IGNORADO] Mensagem vazia | {self.webhook.phone}")
            mensagem = None

        if not self.webhook.fromMe and self.debounce_timeout > 0:
            mensagem = await self.debounce_and_collect_user(mensagem)
        elif self.webhook.fromMe:
            mensagem = await self.debounce_and_collect_assistant(mensagem)

        self.mensagem_consolidada = mensagem

    async def extrair_mensagem(self) -> Optional[str]:
        if mensagem := self.webhook.mensagem_texto:
            return mensagem.strip()

        if audio := self.webhook.url_audio:
            try:
                r = requests.get(audio)
                with open("/tmp/audio.ogg", "wb") as f:
                    f.write(r.content)

                with open("/tmp/audio.ogg", "rb") as audio_file:
                    transcription = openai.Audio.transcribe("whisper-1", audio_file)
                return transcription.get("text", "").strip()
            except Exception as e:
                logger.exception(f"[ERRO AO TRANSCREVER ÁUDIO] {e}")
                return None
        return None

    async def debounce_and_collect_user(self, mensagem: str) -> str:
        redis_key = f"debounce:{self.webhook.phone}:{self.webhook.connectedPhone}"
        task_key = f"{self.webhook.phone}:{self.webhook.connectedPhone}"

        if mensagem:
            await redis_client.rpush(redis_key, mensagem)

        # Cancela tarefas anteriores
        if task_key in debounce_tasks:
            debounce_tasks[task_key].cancel()
            debounce_tasks.pop(task_key, None)

        if task_key in debounce_futures:
            debounce_futures.pop(task_key, None)

        future = asyncio.get_event_loop().create_future()
        debounce_futures[task_key] = future

        debounce_tasks[task_key] = asyncio.create_task(
            self.espera_e_retorna(redis_key, task_key, future, self.debounce_timeout)
        )

        return await future
    
    async def debounce_and_collect_assistant(self, mensagem: str) -> str:
        redis_key = f"debounce:{self.webhook.connectedPhone}:{self.webhook.phone}"
        task_key = f"{self.webhook.connectedPhone}:{self.webhook.phone}"

        if mensagem:
            await redis_client.rpush(redis_key, mensagem)

        # Cancela tarefas anteriores
        if task_key in debounce_tasks:
            debounce_tasks[task_key].cancel()
            debounce_tasks.pop(task_key, None)

        if task_key in debounce_futures:
            debounce_futures.pop(task_key, None)

        future = asyncio.get_event_loop().create_future()
        debounce_futures[task_key] = future

        debounce_tasks[task_key] = asyncio.create_task(
            self.espera_e_retorna(redis_key, task_key, future, self.debounce_timeout_assistant)
        )

        return await future

    async def espera_e_retorna(self, redis_key: str, task_key: str, future: asyncio.Future, debounce: int):
        try:
            await asyncio.sleep(debounce)
            mensagens = await redis_client.lrange(redis_key, 0, -1)
            await redis_client.delete(redis_key)

            resultado = ", ".join(m.decode() if isinstance(m, bytes) else m for m in mensagens)

            if not future.done():
                future.set_result(resultado)
            
            debounce_tasks.pop(task_key, None)
            debounce_futures.pop(task_key, None)

            #logger.info(f"[✅ Consolidado debounce] {resultado}")
        except asyncio.CancelledError:
            logger.info(f"[⛔️ Debounce cancelado] {task_key}")