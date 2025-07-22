import openai, pinecone
from typing import List, Any
from app.utils.logger import logger
from app.config.config import API_KEY_PINECONE

pinecone_client = pinecone.Pinecone(api_key=API_KEY_PINECONE)

class BuscadorChunks:
    def __init__(self, pinecone_index: Any, namespace: Any, pinecone_client: Any = pinecone_client, modelo: str = "text-embedding-ada-002", top_k: int = 3, tentativas: int = 3):
        self.pinecone_index = pinecone_index
        self.namespace = namespace
        self.modelo = modelo
        self.pinecone_client = pinecone_client
        self.pinecone = self.pinecone_client.Index(self.pinecone_index)
        self.top_k = top_k
        self.tentativas = tentativas
        self.best_chunks: List[str] = []

    def formatar_chunks(self, matches: List[dict]) -> List[str]:
        formatted = []
        for match in matches:
            md = match.get("metadata", {})
            # identificar um campo que represente o tipo ou título
            title = md.get("secao", "Info clínica").capitalize()
            lines = [f"**{title}**"]
            for k, v in md.items():
                if k == "secao":
                    continue
                # trata listas
                if isinstance(v, list):
                    v = ", ".join(v)
                lines.append(f"- {k.replace('_', ' ').capitalize()}: {v}")
            formatted.append("\n".join(lines))
        return formatted
    
    async def buscar(self, query: str) -> List[str]:
        for tentativa in range(self.tentativas):
            try:
                embedding = openai.Embedding.create(
                    input=query,
                    model=self.modelo
                )["data"][0]["embedding"]

                results = self.pinecone.query(
                    vector=embedding,
                    top_k=self.top_k,
                    include_metadata=True,
                    namespace=self.namespace
                )

                matches = results.get("matches", [])
                if not matches:
                    logger.warning("[BuscadorChunks] Nenhum match retornado pelo Pinecone.")

                self.best_chunks = self.formatar_chunks(matches)
                return self.best_chunks

            except Exception as e:
                logger.error(f"[BuscadorChunks] Tentativa {tentativa + 1}: {e}")

        logger.critical("[BuscadorChunks] Falha ao buscar chunks após múltiplas tentativas.")
        self.best_chunks = []
        return []
