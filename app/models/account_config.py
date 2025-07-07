from dataclasses import dataclass
from typing import List, Dict, Any


@dataclass
class EtapaFunil:
    id: str
    prompt: str
    obrigatorio: bool


@dataclass
class ConfiguracaoClinica:
    telefone_empresa: str
    prompt_base: str
    tempo_espera_debounce: int
    funil: List[EtapaFunil]

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "ConfiguracaoClinica":
        funil_data = data.get("account_info", {}).get("funil", [])
        funil = [EtapaFunil(**item) for item in funil_data]

        return ConfiguracaoClinica(
            telefone_empresa=data.get("telefone_empresa", ""),
            prompt_base=data.get("account_info", {}).get("prompt_base", ""),
            tempo_espera_debounce=data.get("account_info", {}).get("tempo_espera_debounce", 5),
            funil=funil
        )