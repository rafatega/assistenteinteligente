import openai, pinecone
import asyncio
from typing import List
from tenacity import retry, stop_after_attempt, wait_exponential

from app.utils.logger import logger
from app.config.config import API_KEY_PINECONE

pinecone_client = pinecone.Pinecone(api_key=API_KEY_PINECONE)

class BuscadorChunks:
    def __init__(self, index, namespace, pinecone_client: pinecone.Pinecone = pinecone_client, model="text-embedding-ada-002", top_k=3, min_score: float = 0.75, history_window: int = 4):
        self.client = pinecone_client
        self.index = self.client.Index(index)
        self.namespace = namespace
        self.model = model
        self.top_k = top_k
        self.min_score = min_score
        self.history_window = history_window
        self.best_chunks: List[str] = []

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=5))
    def _embed(self, query: str):
        return openai.Embedding.create(
            input=query,
            model=self.model,
            timeout=10
        )["data"][0]["embedding"]

    def _query(self, embedding):
        resp = self.index.query(
            vector=embedding,
            top_k=self.top_k,
            include_metadata=True,
            namespace=self.namespace
        )
        return resp.get("matches", [])

    def formatar_chunks(self, matches) -> List[str]:
        output = []
        for m in sorted(matches, key=lambda x: x["score"], reverse=True):
            md    = m["metadata"]
            texto = md.get("texto", "")
            score = m["score"]
            bloco = [
                f"> **Score de contexto**: {score:.2f}",
                f"{texto}"
            ]

            for k, v in md.items():
                if k == "texto":
                    continue
                if isinstance(v, list):
                    v = ", ".join(v)
                # adiciona cada metadado no bloco
                bloco.append(f"- {k}: {v}")

            output.append("\n".join(bloco))
        return output


    async def buscar(self, query: str, historico_usuario: List[str] = None) -> List[str]:
        """
        current_query: mensagem recente do usuário
        history: lista de todas as mensagens do usuário (self.mensagens_usuario)
        """
        # 1) montar o texto que vai pro embed
        if historico_usuario:
            # pega só as últimas `history_window` mensagens
            últimas = historico_usuario[-self.history_window:]
            # junta com a query atual
            full_query = "\n".join(últimas + [query])
        else:
            full_query = query

        # 2) gerar embedding desse full_query
        emb = await asyncio.to_thread(self._embed, full_query)

        # 3) buscar no Pinecone como antes
        matches = await asyncio.to_thread(self._query, emb)
        # 4) Aplica threshold
        matches = [m for m in matches if m["score"] >= self.min_score]

        if not matches:
            default_msg = ("Sem contexto de acordo com a mensagem e histórico do cliente, se necessário, peça para reformular ou especificar melhor sua dúvida.")
            logger.warning("Sem chunks acima do limiar")
            # salva e retorna a string única
            self.best_chunks = [default_msg]
            return self.best_chunks
        
        #logger.info(f"Match CRU: {matches}")
        self.best_chunks = self.formatar_chunks(matches)
        logger.info(f"BestChunks: {self.best_chunks}")
        return self.best_chunks
