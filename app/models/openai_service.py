import openai
import json
import textwrap
from typing import List, Dict, Union
from app.utils.logger import logger
from dataclasses import dataclass

@dataclass
class ChatInput:
    mensagem: str
    best_chunks: List[str]
    historico: Union[str, List[Dict]]
    prompt_base: str
    prompt_state: str
    user_data: str

class ChatResponder:
    def __init__(self, chat_input: ChatInput, modelo="gpt-4o-mini", modelo_fallback="gpt-3.5-turbo", tentativas=3, temperature=0.4, top_p=0.9, max_tokens=200):
        self.input = chat_input
        self.modelo = modelo
        self.modelo_fallback = modelo_fallback
        self.tentativas = tentativas
        self.temperature = temperature
        self.top_p = top_p
        self.max_tokens = max_tokens
        self.resposta = ""

    def formatar_historico(self) -> str:
        historico_raw = self.input.historico
        if isinstance(historico_raw, str):
            try:
                historico_raw = json.loads(historico_raw)
            except json.JSONDecodeError:
                return "(Histórico inválido ou não disponível.)"

        if not historico_raw:
            return "(Sem histórico de conversa até o momento.)"

        role_map = {
            "system": "🧠 Sistema",
            "assistant": "🤖 Assistente",
            "user": "🧍 Paciente"
        }

        return "\n".join(
            f"{role_map.get(m.get('role'), m.get('role'))}: {m.get('content', '').strip()}"
            for m in historico_raw
        )

    def build_system_content(self) -> str:
        return f"""
[INSTRUÇÕES DA DIANA]
{textwrap.dedent(self.input.prompt_base or "Sem instruções da Diana até o momento.").strip()}

[ESTADO DO FUNIL]
{textwrap.dedent(self.input.prompt_state or "Sem estado de funil até o momento.").strip()}

[HISTÓRICO DE CONVERSA]
{self.formatar_historico()}

[INFORMAÇÕES DO PACIENTE]
{self.input.user_data or "Sem informações adicionais do paciente."}

[CONTEXTO DA CLÍNICA]
{"\n".join(self.input.best_chunks) or "Sem informações adicionais da clínica."}
"""

    def build_messages(self, system_content: str) -> List[Dict]:
        return [
            {"role": "system", "content": system_content},
            {"role": "user", "content": self.input.mensagem}
        ]

    async def generate(self) -> str:
        contexto_cru = self.build_system_content().strip()
        contexto_completo = self.build_messages(contexto_cru)
        logger.info(f"Contexto: {contexto_completo}")

        for attempt in range(self.tentativas):
            model = self.modelo if attempt < self.tentativas - 1 else self.modelo_fallback
            try:
                response = await openai.ChatCompletion.acreate(
                    model=model,
                    messages=contexto_completo,
                    temperature=self.temperature,
                    top_p=self.top_p,
                    max_tokens=self.max_tokens
                )
                self.resposta = response.choices[0].message.content.strip()
                return self.resposta
            except Exception as e:
                logger.error(f"[ChatResponder] erro (tentativa {attempt+1}, modelo {model}): {e}")

        logger.critical("[ChatResponder] falha total ao gerar resposta.")
        self.resposta = "Desculpe, ocorreu um erro ao processar sua pergunta."
        return self.resposta
