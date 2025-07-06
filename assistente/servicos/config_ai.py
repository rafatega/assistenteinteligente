import time
import openai
import pinecone
import requests
from typing import List, Dict, Optional

from assistente.core.config import API_KEY_OPENAI, API_KEY_PINECONE, PINECONE_INDEX_NAME, PINECONE_NAMESPACE

# Inicializa APIs
openai.api_key = API_KEY_OPENAI
pinecone_client = pinecone.Pinecone(api_key=API_KEY_PINECONE)
pinecone_index = pinecone_client.Index(PINECONE_INDEX_NAME)

RETRY_ATTEMPTS = 3
EMBEDDING_MODEL = "text-embedding-ada-002"
CHAT_MODEL = "gpt-4o-mini"
FALLBACK_MODEL = "gpt-3.5-turbo"

async def extract_message_content(body: dict) -> str | None:
    # Se tiver campo "text", use
    if msg := body.get("text", {}).get("message"):
        return msg.strip()

    # Se for áudio recebido
    audio = body.get("audio")
    if audio and (url := audio.get("audioUrl")):
        try:
            r = requests.get(url)
            with open("/tmp/audio.ogg", "wb") as f:
                f.write(r.content)

            with open("/tmp/audio.ogg", "rb") as audio_file:
                transcription = openai.Audio.transcribe("whisper-1", audio_file)

            texto = transcription.get("text")
            return texto.strip() if texto else None
        except Exception as e:
            logger.exception(f"[ERRO AO TRANSCREVER ÁUDIO] {e}")
            return None

    return None