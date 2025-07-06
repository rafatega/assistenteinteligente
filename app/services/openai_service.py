import requests
import openai

from app.utils.logger import logger

# Inicializa APIs
openai.api_key = API_KEY_OPENAI

async def extract_message_content(received_webhook: dict) -> str | None:
    if mensagem := received_webhook.mensagem_texto:
        return mensagem.strip()

    # Se for áudio recebido
    if audio := received_webhook.url_audio:
        try:
            r = requests.get(audio)
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