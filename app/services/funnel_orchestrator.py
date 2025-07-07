import json
import asyncio
from enum import Enum
from typing import Optional, Dict, Any, TypedDict

# -- Constants
REDIS_PREFIX = "funnel:"
SUPABASE_TABLE = "user_funnel_data"

def process_funnel_message(numero: str, mensagem: str, nome_cliente: str) -> None:
    pass