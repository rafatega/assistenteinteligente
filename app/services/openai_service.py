import requests

async def extract_message_content(body: dict) -> str | None:
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