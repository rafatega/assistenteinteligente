from supabase import create_client, Client
from app.config.config import SUPABASE_URL, SUPABASE_KEY
from datetime import datetime, timedelta, timezone

# Defina o offset do seu fuso horário (Brasília normalmente é UTC-3)
fuso_brasilia = timezone(timedelta(hours=-3))

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def registrar_interacao(interacoes):
    for interacao in interacoes:
        interacao["anomesdia"] = datetime.now(fuso_brasilia).strftime("%Y%m%d")
        interacao["horaminuto"] = datetime.now(fuso_brasilia).strftime("%H%M")
    try:
        supabase.table("sor_table").insert(interacoes).execute()
    except Exception as e:
        print(f"Erro ao registrar interação: {e}")