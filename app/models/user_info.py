import json
from typing import Optional, Any, Dict
from dataclasses import dataclass, field
from app.config.redis_client import redis_client
from app.config.supabase_client import supabase
from app.utils.logger import logger

@dataclass
class UserInfo:
    state: str
    data: Dict[str, Any] = field(default_factory=dict)

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "UserInfo":
        return UserInfo(
            state=data.get("state", ""),
            data=data.get("data", {})
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "state": self.state,
            "data": self.data
        }

class UserInfoService:
    TABLE = "user_data"
    FIELD = "user_info"
                                                                                                            #43200
    def __init__(self, telefone_cliente: str, telefone_usuario: str, funnel_info, cache_ttl: Optional[int] = 180, redis_client: Any = redis_client, supabase_client: Any = supabase):
        self.telefone_cliente = telefone_cliente
        self.telefone_usuario = telefone_usuario
        self.funnel_info = funnel_info
        self.cache_ttl = cache_ttl
        self.redis_client = redis_client
        self.supabase_client = supabase_client
        self.user_info: Optional[UserInfo] = None

    async def get(self) -> UserInfo:
        key = f"{self.FIELD}:{self.telefone_cliente}:{self.telefone_usuario}"

        raw = await self.redis_client.get(key)
        if raw:
            try:
                self.user_info = UserInfo.from_dict(json.loads(raw))
                return self.user_info
            except json.JSONDecodeError:
                logger.warning(f"[UserInfoService] JSON inválido no cache Redis: {key}")
                await self.redis_client.delete(key)

        self.user_info = await self.get_from_supabase(key)
        return self.user_info

    async def get_from_supabase(self, redis_key: str) -> UserInfo:
        try:
            res = self.supabase_client.table(self.TABLE)\
                .select(self.FIELD)\
                .eq("telefone_cliente", self.telefone_cliente)\
                .eq("telefone_usuario", self.telefone_usuario)\
                .order("id", desc=True)\
                .limit(1)\
                .execute()

            if res.data:
                raw = res.data[0].get(self.FIELD)
                if raw:
                    user_info = UserInfo.from_dict(raw)
                    user_info = self.sync_with_funnel(user_info)
                    await self.redis_client.set(redis_key, json.dumps(user_info.to_dict()), ex=self.cache_ttl)
                    return user_info

        except Exception as e:
            logger.exception(f"[UserInfoService] Erro ao consultar Supabase: {e}")

        logger.info(f"[UserInfoService] Criando novo user_info para {self.telefone_usuario}")
        return await self.create_initial_user_info(redis_key)

    async def create_initial_user_info(self, redis_key: str) -> UserInfo:
        tracking_dict = self.funnel_info.to_tracking_dict(estado_atual=None)
        initial_info = UserInfo(**tracking_dict)
        try:
            await self.redis_client.set(redis_key, json.dumps(initial_info.to_dict()), ex=self.cache_ttl)
            logger.info(f"[UserInfoService] Registro criado ou atualizado para {self.telefone_usuario}")
        except Exception as e:
            logger.exception(f"[UserInfoService] Erro ao criar user_info: {e}")
            raise RuntimeError("Erro ao criar user_info")

        return initial_info

    def sync_with_funnel(self, user_info: UserInfo) -> UserInfo:
        funnel_ids = [etapa.id for etapa in self.funnel_info.funil]
        updated_data = {
            etapa_id: user_info.data.get(etapa_id, None)
            for etapa_id in funnel_ids
        }
        updated_state = user_info.state if user_info.state in funnel_ids else (funnel_ids[0] if funnel_ids else "")
        return UserInfo(state=updated_state, data=updated_data)
