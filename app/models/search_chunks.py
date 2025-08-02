import openai, pinecone
from typing import List
from tenacity import retry, stop_after_attempt, wait_exponential

from app.utils.logger import logger
from app.config.config import API_KEY_PINECONE

pinecone_client = pinecone.Pinecone(api_key=API_KEY_PINECONE)

class BuscadorChunks:
    def __init__(self, index, namespace, pinecone_client: pinecone.Pinecone = pinecone_client, model="text-embedding-ada-002", top_k=3, min_score: float = 0.8):
        self.client = pinecone_client
        self.index = self.client.Index(index)
        self.namespace = namespace
        self.model = model
        self.top_k = top_k
        self.min_score = min_score
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
            md = m["metadata"]
            texto = md.get("texto", "")
            bloco = [f"> {texto}", f"**Score**: {m['score']:.2f}"]
            for k, v in md.items():
                if k == "texto": continue
                if isinstance(v, list): v = ", ".join(v)
                bloco.append(f"- **{k.replace('_',' ').capitalize()}**: {v}")
            output.append("\n".join(bloco))
        return output

    def buscar(self, query: str) -> List[str]:
        emb = self._embed(query)
        matches = self._query(emb)
        # aplica threshold
        matches = [m for m in matches if m["score"] >= self.min_score]
        if not matches:
            default_msg = ("Sem contexto de acordo com a mensagem e histórico do cliente, se necessário, peça para reformular ou especificar melhor sua dúvida.")
            logger.warning("Sem chunks acima do limiar")
            # salva e retorna a string única
            self.best_chunks = [default_msg]
            return self.best_chunks
            
        self.best_chunks = self.formatar_chunks(matches)
        logger.info(f"BestChunks: {self.best_chunks}")
        return self.best_chunks
