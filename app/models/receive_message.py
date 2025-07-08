from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from dataclasses import dataclass

class WebhookMessage(BaseModel):
    connectedPhone: str
    isGroup: bool
    phone: str
    fromMe: bool
    momment: int
    senderName: Optional[str] = None
    text: Optional[dict] = None
    audio: Optional[dict] = None
    mensagem: Optional[str] = None

    @property
    def mensagem_texto(self) -> Optional[str]:
        if self.text:
            return self.text.get("message")
        return None

    @property
    def url_audio(self) -> Optional[str]:
        if self.audio:
            return self.audio.get("audioUrl")
        return None
    
    def agrupar_mensagem(self, texto_agrupado: str):
        self.mensagem = texto_agrupado

@dataclass
class ConfigInfo:
    tempo_espera_debounce: int
    pinecone_index_name: str
    pinecone_namespace: str
    zapi_instance_id: str
    zapi_token: str

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "ConfigInfo":
        return ConfigInfo(
            tempo_espera_debounce=data.get("tempo_espera_debounce", 8),
            pinecone_index_name=data.get("pinecone_index_name", ""),
            pinecone_namespace=data.get("pinecone_namespace", ""),
            zapi_instance_id=data.get("zapi_instance_id", ""),
            zapi_token=data.get("zapi_token", "")
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tempo_espera_debounce": self.tempo_espera_debounce,
            "pinecone_index_name": self.pinecone_index_name,
            "pinecone_namespace": self.pinecone_namespace,
            "zapi_instance_id": self.zapi_instance_id,
            "zapi_token": self.zapi_token,
        }

@dataclass
class EtapaFunil:
    id: str
    prompt: str
    obrigatorio: bool
    aliases: Optional[Dict[str, Any]] = None
    regex: Optional[List[str]] = None

@dataclass
class FunnelInfo:
    prompt_base: str
    funil: List[EtapaFunil]

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "FunnelInfo":
        funil_raw = data.get("funil", [])
        funil = [EtapaFunil(**item) for item in funil_raw]
        return FunnelInfo(
            prompt_base=data.get("prompt_base", ""),
            funil=funil
        )