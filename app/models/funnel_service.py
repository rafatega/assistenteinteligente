from dataclasses import dataclass
from typing import Any, Dict, List, Optional
import json

from app.config.redis_client import redis_client
from app.config.supabase_client import supabase
from app.utils.logger import logger


@dataclass
class EtapaFunil:
    id: str
    prompt: str
    obrigatorio: bool
    permite_nova_entrada: bool = False
    fallback_llm: Optional[Any] = None
    aliases: Optional[Dict[str, Any]] = None
    regex: Optional[List[str]] = None

@dataclass
class FunnelInfo:
    prompt_base: str
    funil: List[EtapaFunil]
    prompt_apresentacao_inicial: str

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "FunnelInfo":
        funil_raw = data.get("funil", [])
        funil = [EtapaFunil(**item) for item in funil_raw]
        return FunnelInfo(
            prompt_base=data.get("prompt_base", ""),
            funil=funil,
            prompt_apresentacao_inicial=data.get("prompt_apresentacao_inicial", "")
        )
    
    def to_tracking_dict(self, preenchidos: Dict[str, Any] = None, estado_atual: Optional[str] = None) -> Dict[str, Any]:
        preenchidos = preenchidos or {}
        return {
            "state": estado_atual or "",
            "data": {
                etapa.id: preenchidos.get(etapa.id, None)
                for etapa in self.funil
            }
        }

class FunnelService:
    TABLE = "account_data"
    FIELD = "funnel_info"
                                                                    #43200
    def __init__(self, telefone_cliente: str, cache_ttl: Optional[int] = 43200, redis_client: Any = redis_client, supabase_client: Any = supabase):
        self.telefone = telefone_cliente
        self.cache_ttl = cache_ttl
        self.redis_client = redis_client
        self.supabase_client = supabase_client
        self.funnel: Optional[FunnelInfo] = None

    async def get(self) -> FunnelInfo:
        key = f"{self.FIELD}:{self.telefone}"
        raw = await self.redis_client.get(key)
        if raw:
            try:
                self.funnel = FunnelInfo.from_dict(json.loads(raw))
                # Eu tirei os returns dos outros, mas é interessante deixar...
                return self.funnel
            except json.JSONDecodeError:
                await self.redis_client.delete(key)
                logger.warning(f"JSON inválido em cache: {key}")

        res = self.supabase_client.table(self.TABLE)\
            .select(self.FIELD)\
            .eq("telefone_cliente", self.telefone)\
            .order("id", desc=True)\
            .limit(1)\
            .single()\
            .execute()

        data = res.data or {}
        funnel = data.get(self.FIELD)
        if not funnel:
            logger.error(f"Nenhum funnel encontrado para {self.telefone}")
            raise RuntimeError
        
        self.funnel = FunnelInfo.from_dict(funnel)
        await self.redis_client.set(key, json.dumps(funnel), ex=self.cache_ttl)
        return self.funnel