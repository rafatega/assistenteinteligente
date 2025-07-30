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
    
    def clear_user_supabase_record(self) -> int:
        """
        Exclui o registro no Supabase onde id_cliente_usuario == self.key.
        
        Retorna o número de registros excluídos.
        """
        try:
            response = (
                supabase
                .table("user_data")
                .delete()
                .eq("id_cliente_usuario", self.key)
                .execute()
            )
            # Supabase retorna a lista de itens deletados em response.data
            deleted_rows = len(response.data or [])
            logger.info(
                f"✔️ Registros Supabase excluídos ({deleted_rows}) "
                f"em 'user_data' para id_cliente_usuario='{self.key}'"
            )
            return "Deletado"
        except Exception as e:
            logger.error(
                f"❗ Falha ao excluir registro Supabase para id_cliente_usuario='{self.key}': {e}"
            )
            raise
    
    def clear_user_redis_record(self) -> int:
        """
        Exclui os registros Redis para:
          - history:{self.key}
          - user_info:{self.key}

        Retorna o número de chaves excluídas.
        """
        history_key = f"history:{self.key}"
        user_info_key = f"user_info:{self.key}"

        try:
            # delete pode receber múltiplas chaves
            deleted_count = self.redis.delete(history_key, user_info_key)
            logger.info(
                f"✔️ Chaves Redis excluídas ({deleted_count}): "
                f"'{history_key}', '{user_info_key}'"
            )
            return "Deletado"
        except Exception as e:
            logger.error(
                f"❗ Falha ao excluir chaves BD1 '{history_key}' e '{user_info_key}': {e}"
            )
            # relança ou retorna zero conforme a política de erro desejada
            raise
    
    def clear_client_redis_record(self) -> int:
        """
        Exclui os registros Redis para:
          - history:{self.key}
          - user_info:{self.key}

        Retorna o número de chaves excluídas.
        """
        config_key = f"config_info:{self.telefone_cliente}"
        funnel_key = f"funnel_info:{self.telefone_cliente}"

        try:
            # delete pode receber múltiplas chaves
            deleted_count = self.redis.delete(config_key, funnel_key)
            logger.info(
                f"✔️ Chaves Redis excluídas ({deleted_count}): "
                f"'{config_key}', '{funnel_key}'"
            )
            return "Deletado"
        except Exception as e:
            logger.error(
                f"❗ Falha ao excluir chaves Redis '{config_key}' e '{funnel_key}': {e}"
            )
            # relança ou retorna zero conforme a política de erro desejada
            raise
    
    def developer_mode(self, cmd):
        if cmd == "/adminresetuser":
            # Remove tanto Redis quanto Supabase
            redis_deleted = self.clear_user_redis_record()
            supabase_deleted = self.clear_user_supabase_record()
            retorno = (
                f"✅ Usuário resetado:\n"
                f"- BD1: {redis_deleted}\n"
                f"- BD2: {supabase_deleted}"
            )

        elif cmd == "/adminresetclient":
            # Somente Redis (ex.: não mexe no Supabase)
            redis_deleted = self.clear_client_redis_record()
            retorno = (
                f"✅ Cliente resetado:\n"
                f"- BD1: {redis_deleted}"
            )

        return retorno

    