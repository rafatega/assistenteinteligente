from app.models.receive_message import WebhookMessage
from app.services.openai_service import extract_message_content

async def process_message(body: dict) -> dict:
    # Transforma o dict bruto em objeto tipado
    received_webhook = WebhookMessage(**body)

    mensagem = await extract_message_content(received_webhook)

    numero = received_webhook.phone
    telefone_empresa = received_webhook.connectedPhone
    nome_cliente = received_webhook.senderName

    print(received_webhook)

    if received_webhook.mensagem_texto:
        mensagem = received_webhook.mensagem_texto.strip()
        print("Texto recebido:", mensagem)

    if received_webhook.url_audio:
        print("Áudio recebido:", received_webhook.url_audio)

    return {"status": "ok"}
