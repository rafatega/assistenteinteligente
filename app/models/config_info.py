import json
from app.utils.logger import logger
from dataclasses import dataclass
from typing import Optional, Any
from app.config.redis_client import redis_client
from app.config.supabase_client import supabase

@dataclass
class ConfigInfo:
    zapi_token: str
    zapi_instance_id: str
    pinecone_namespace: str
    pinecone_index_name: str
    tempo_espera_debounce: Optional[int] = 0
    chave_parar_atendimento: Optional[str] = None

    @classmethod
    def from_dict(cls, data: dict) -> "ConfigInfo":
        return cls(
            zapi_token=data.get("zapi_token", ""),
            zapi_instance_id=data.get("zapi_instance_id", ""),
            pinecone_namespace=data.get("pinecone_namespace", ""),
            pinecone_index_name=data.get("pinecone_index_name", ""),
            tempo_espera_debounce=data.get("tempo_espera_debounce", 0),
            chave_parar_atendimento=data.get("chave_parar_atendimento", None)
        )

    def to_dict(self) -> dict:
        return {
            "zapi_token": self.zapi_token,
            "zapi_instance_id": self.zapi_instance_id,
            "pinecone_namespace": self.pinecone_namespace,
            "pinecone_index_name": self.pinecone_index_name,
            "tempo_espera_debounce": self.tempo_espera_debounce,
            "chave_parar_atendimento": self.chave_parar_atendimento
        }
    
    def desativar_assistente(self, mensagem: Optional[str]) -> bool:
        logger.info(f"Parando assistente, humando em atendimento, chave: {self.chave_parar_atendimento}")
        return (
            self.chave_parar_atendimento is not None and
            mensagem is not None and
            self.chave_parar_atendimento in mensagem
        )

class ConfigService:                                                                                                                    #43200
    def __init__(self, telefone_cliente: str, redis_client: Any = redis_client, supabase_client: Any = supabase, cache_ttl: Optional[int] = 180, config: Optional[ConfigInfo] = None):
        self.telefone_cliente = telefone_cliente
        self.redis_client = redis_client
        self.supabase = supabase_client
        self.cache_ttl = cache_ttl
        self.table = "account_data"
        self.field = "config_info"
        self.config = config

    async def get(self) -> ConfigInfo:
        if self.config:
            return self.config  # ← Reuso

        key = f"{self.field}:{self.telefone_cliente}"
        config = await self.get_from_cache(key)
        if not config:
            config = await self.get_from_supabase()
            await self.set_cache(key, config)

        self.config = config
        #return config

    async def get_from_cache(self, key: str) -> ConfigInfo | None:
        raw = await self.redis_client.get(key)
        if not raw:
            return None
        try:
            return ConfigInfo.from_dict(json.loads(raw))
        except json.JSONDecodeError:
            logger.warning(f"[ConfigService] JSON inválido no cache Redis: {key}")
            await self.redis_client.delete(key)
            return None

    async def get_from_supabase(self) -> ConfigInfo:
        try:
            res = self.supabase.table(self.table) \
                .select(self.field) \
                .eq("telefone_cliente", self.telefone_cliente) \
                .order("id", desc=True) \
                .limit(1) \
                .single() \
                .execute()

            data = res.data or {}
            raw = data.get(self.field)
            if not raw:
                logger.error(f"[ConfigService] Campo '{self.field}' ausente para telefone {self.telefone_cliente}")
                raise RuntimeError(f"Configurações ausentes para {self.telefone_cliente}")

            return ConfigInfo.from_dict(raw)

        except Exception as e:
            logger.exception(f"[ConfigService] Erro ao buscar no Supabase: {e}")
            raise RuntimeError(f"Erro ao carregar config para {self.telefone_cliente}")

    async def set_cache(self, key: str, config: ConfigInfo):
        try:
            payload = config.to_dict()
            await self.redis_client.set(key, json.dumps(payload), ex=self.cache_ttl)
        except Exception as e:
            logger.warning(f"[ConfigService] Falha cachear config para {key}: {e}")
    
    def __getattr__(self, attr):
        if self.config:
            return getattr(self.config, attr)
        raise AttributeError(f"Config ainda não carregado. Chame 'await .get()' antes de acessar '{attr}'")
    
    def __repr__(self):
        return f"<ConfigService telefone={self.telefone_cliente}>"
