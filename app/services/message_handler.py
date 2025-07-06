from app.models.receive_message import WebhookMessage

async def process_message(body: dict) -> dict:
    # Transforma o dict bruto em objeto tipado
    received_webhook = WebhookMessage(**body)

    numero = received_webhook.phone
    telefone_empresa = received_webhook.connectedPhone
    nome_cliente = received_webhook.senderName

    print(f"Recebendo mensagem de {nome_cliente} ({numero}), telefone empresa: {telefone_empresa})")

    if received_webhook.mensagem_texto:
        print("Texto recebido:", received_webhook.mensagem_texto)

    if received_webhook.url_audio:
        print("Áudio recebido:", received_webhook.url_audio)

    return {"status": "ok"}
