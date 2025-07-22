import openai
import json
import textwrap
from typing import List, Dict, Union, Optional, Any
from app.utils.logger import logger
from dataclasses import dataclass

@dataclass
class ChatInput:
    mensagem: str
    best_chunks: List[str]
    historico: Union[str, List[Dict]]
    prompt_base: str
    prompt_state: str
    user_data: Dict[str, Any]  # Agora user_data como dict
    funnel_etapas: List[Any]   # Etapas do funil para formatação dinâmica

class ChatResponder:
    def __init__(
        self,
        chat_input: ChatInput,
        modelo="gpt-4o-mini",
        modelo_fallback="gpt-3.5-turbo",
        tentativas: int=3,
        temperature: float=0.4,
        top_p: float=0.9,
        max_tokens: int=200
    ):
        self.input = chat_input
        self.modelo = modelo
        self.modelo_fallback = modelo_fallback
        self.tentativas = tentativas
        self.temperature = temperature
        self.top_p = top_p
        self.max_tokens = max_tokens
        self.resposta: str = ""

    def formatar_historico(self) -> str:
        historico = self.input.historico
        if isinstance(historico, str):
            try:
                historico = json.loads(historico)
            except json.JSONDecodeError:
                return "(Histórico inválido ou não disponível.)"
        if not historico:
            return "(Sem histórico de conversa até o momento.)"
        role_map = {"system":"🧠 Sistema","assistant":"🤖 Assistente","user":"🧍 Paciente"}
        return "\n".join(
            f"{role_map.get(m.get('role'), m.get('role'))}: {m.get('content','').strip()}"
            for m in historico
        )

    def formatar_userinfo(self) -> str:
        data = self.input.user_data.get("data", {})
        estado = self.input.user_data.get("state", "")
        linhas = [f"📌 Etapa atual: {estado or '(nenhuma)'}", "📋 Dados coletados:"]
        for etapa in self.input.funnel_etapas:
            valor = data.get(etapa.id)
            nome_legivel = etapa.id.replace("_", " ").capitalize()
            if valor is None:
                linhas.append(f"- {nome_legivel}: ❌ Ainda não informado")
            else:
                linhas.append(f"- {nome_legivel}: ✅ {valor}")
        return "\n".join(linhas)

    def build_system_content(self) -> str:
        return "\n".join([
            "[INSTRUÇÕES DA DIANA]",
            textwrap.dedent(self.input.prompt_base or "").strip(),
            "",
            "[ESTADO DO FUNIL]",
            textwrap.dedent(self.input.prompt_state or "").strip(),
            "",
            "[HISTÓRICO DE CONVERSA]",
            self.formatar_historico(),
            "",
            "[INFORMAÇÕES DO CLIENTE]",
            self.formatar_userinfo(),
            "",
            "[CONTEXTO DA CLÍNICA]",
            "\n".join(self.input.best_chunks) or "Sem informações adicionais da clínica."
        ]).strip()

    def build_messages(self, system_content: str) -> List[Dict]:
        return [
            {"role": "system", "content": system_content},
            {"role": "user", "content": self.input.mensagem.strip()}
        ]

    async def generate(self) -> str:
        system_msg = self.build_system_content()
        messages = self.build_messages(system_msg)
        logger.info("=== CONTEXTO ENVIADO AO GPT ===")
        logger.info(system_msg.replace("\n", "\\n"))  # Log mais legível
        for i in range(self.tentativas):
            model = self.modelo if i < self.tentativas - 1 else self.modelo_fallback
            try:
                response = await openai.ChatCompletion.acreate(
                    model=model,
                    messages=messages,
                    temperature=self.temperature,
                    top_p=self.top_p,
                    max_tokens=self.max_tokens
                )
                self.resposta = response.choices[0].message.content.strip()
                return self.resposta
            except Exception as e:
                logger.error(f"[ChatResponder] erro (tentativa {i+1}, modelo {model}): {e}")
        logger.critical("[ChatResponder] falha total ao gerar resposta.")
        self.resposta = "Desculpe, ocorreu um erro ao processar sua pergunta."
        return self.resposta
