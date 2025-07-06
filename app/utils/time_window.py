from datetime import datetime, time
from zoneinfo import ZoneInfo
from fastapi import HTTPException, status

TIMEZONE = "America/Sao_Paulo"
START = time(0, 0)  # 18:00
END   = time(23, 59)   # 09:00

def ensure_allowed_time() -> None:
    """
    Garante que a requisição está dentro da janela 18:00–09:00
    no fuso America/Sao_Paulo. Lança HTTPException caso contrário.
    """
    now = datetime.now(ZoneInfo(TIMEZONE)).time()
    # Permite se for maior igual às 18:00 OU menor que 09:00
    if not (now >= START or now < END):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acesso permitido apenas entre 00:00 e 23:59 (horário de São Paulo)"
        )
