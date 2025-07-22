import re
import httpx
import asyncio
from typing import List

from app.config.config import ZAPI_PHONE_HEADER
from app.utils.logger import logger


class RespostaSegmentada:
    ABBREVIATIONS = [r'Sr', r'Sra', r'Dr', r'Dra', r'Av', r'Ed', r'Prof', r'Profa', r'Profª', r'Ex', r'Exa', r'Adm', r'Assoc', r'etc', r'p\.e', r'p\.ex']
    PLACEHOLDER = '<DOT>'
    # Regex para detectar enumerações numéricas (topicos) como '1. ', '2. ' etc.
    ENUM_PATTERN = re.compile(r'(?m)(?P<number>\b\d+)\.(?=\s)')

    def __init__(self, resposta_ia: str):
        self.resposta_ia = resposta_ia
        self.resposta_segmentada = self._segmentar()

    def _segmentar(self) -> List[str]:
        texto = self.resposta_ia
        for abbr in self.ABBREVIATIONS:
            texto = re.sub(rf"\b{abbr}\.", f"{abbr}{self.PLACEHOLDER}", texto)
        texto = self.ENUM_PATTERN.sub(lambda m: f"{m.group('number')}{self.PLACEHOLDER}", texto)
        partes = re.split(r'\.\s+', texto)
        frases = []
        for parte in partes:
            seg = parte.strip()
            if not seg:
                continue
            seg = seg.replace(self.PLACEHOLDER, '.')
            if not seg.endswith(('.', '?', '!')):
                seg += '.'
            frases.append(seg)
        return frases

    def __iter__(self):
        return iter(self.resposta_segmentada)

class MensagemDispatcher:
    def __init__(self, numero_destino: str, resposta: str, zapi_instance_id: str, zapi_token: str, zapi_phone_header: str = ZAPI_PHONE_HEADER, retries: int = 3, delay_typing: int = 3, delay_between: float = 0, timeout: int = 10):
        self.numero = numero_destino
        self.segmentos = RespostaSegmentada(resposta)
        self.url = f"https://api.z-api.io/instances/{zapi_instance_id}/token/{zapi_token}/send-text"
        self.headers = {
            'client-token': zapi_phone_header,
            'Content-Type': "application/json"
        }
        self.retries = retries
        self.delay_typing = delay_typing
        self.delay_between = delay_between
        self.timeout = timeout
        self.client = httpx.AsyncClient(timeout=self.timeout)

    async def enviar_segmento(self, segmento: str) -> dict:
        payload = {
            "phone": self.numero,
            "message": segmento,
            "delayMessage": 0,
            "delayTyping": self.delay_typing
        }
        for attempt in range(1, self.retries + 1):
            try:
                logger.info(f"Enviando segmento {attempt}/{self.retries}: {segmento}")
                resp = await self.client.post(self.url, json=payload, headers=self.headers)
                if resp.status_code == 200:
                    return {"segmento": segmento, "status": resp.status_code}
                else:
                    raise Exception(f"Status {resp.status_code}")
            except Exception as e:
                logger.error(f"Erro no envio (tentativa {attempt}): {e}")
                await asyncio.sleep(1)
        logger.critical(f"Falha total no segmento — enfileirando: {segmento}")
        return {"segmento": segmento, "status": None}

    async def enviar_resposta(self) -> List[dict]:
        results = []
        for segment in self.segmentos:
            res = await self.enviar_segmento(segment)
            results.append(res)
            await asyncio.sleep(self.delay_between)
        await self.client.aclose()
        return results