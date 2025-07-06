
async def processa_mensagem(body: dict) -> dict:
    numero = body.get("phone")
    telefone_empresa = body.get("connectedPhone")
    nome_cliente = body.get("senderName")
    print(f"Recebendo mensagem de {nome_cliente} ({numero}), telefone empresa: {telefone_empresa})")
