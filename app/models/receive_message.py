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
class EtapaFunil:
    id: str
    prompt: str
    obrigatorio: bool


@dataclass
class ConfiguracaoCliente:
    telefone_empresa: str
    prompt_base: str
    tempo_espera_debounce: int
    funil: List[EtapaFunil]

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "ConfiguracaoCliente":
        funil_data = data.get("account_info", {}).get("funil", [])
        funil = [EtapaFunil(**item) for item in funil_data]

        return ConfiguracaoCliente(
            telefone_empresa=data.get("telefone_empresa", ""),
            prompt_base=data.get("account_info", {}).get("prompt_base", ""),
            tempo_espera_debounce=data.get("account_info", {}).get("tempo_espera_debounce", 5),
            funil=funil
        )