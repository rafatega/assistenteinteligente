from typing import Any
from app.utils.logger import logger
from app.config.redis_client import redis_client
from app.config.supabase_client import supabase

class DeveloperMode:
    def __init__(self, telefone_cliente: str, telefone_usuario: str, redis_client: Any = redis_client):
        self.telefone_cliente = telefone_cliente
        self.telefone_usuario = telefone_usuario
        self.redis = redis_client
        self.key = f"{telefone_cliente}:{telefone_usuario}"
    
    def clear_user_redis_record(self) -> int:
        history_key   = f"history:{self.key}"
        user_info_key = f"user_info:{self.key}"
        deleted_count = self.redis.delete(history_key, user_info_key)
        logger.info(f"✔️ Redis delete count={deleted_count} for {history_key}, {user_info_key}")
        return deleted_count

    def clear_user_supabase_record(self) -> int:
        response = (
            supabase
            .table("user_data")
            .delete()
            .eq("id_cliente_usuario", self.key)
            .execute()
        )
        deleted_rows = len(response.data or [])
        logger.info(f"✔️ Supabase delete count={deleted_rows} for id={self.key}")
        return deleted_rows

    def clear_client_redis_record(self) -> int:
        config_key = f"config_info:{self.telefone_cliente}"
        funnel_key = f"funnel_info:{self.telefone_cliente}"
        deleted_count = self.redis.delete(config_key, funnel_key)
        logger.info(f"✔️ Redis delete count={deleted_count} for {config_key}, {funnel_key}")
        return deleted_count

    def developer_mode(self, cmd: str) -> str:
        if cmd == "/adminresetuser":
            r = self.clear_user_redis_record()
            s = self.clear_user_supabase_record()
            return (
                f"✅ Usuário resetado:\n"
                f"- Redis: {r} chave(s) removida(s)\n"
                f"- Supabase: {s} registro(s) removido(s)"
            )
        elif cmd == "/adminresetclient":
            r = self.clear_client_redis_record()
            return (
                f"✅ Cliente resetado:\n"
                f"- Redis: {r} chave(s) removida(s)"
            )
        else:
            raise ValueError(f"Comando desconhecido: {cmd}")