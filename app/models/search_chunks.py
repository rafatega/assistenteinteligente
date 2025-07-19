import openai
from typing import List
from app.utils.logger import logger

class BuscadorChunks:
    def __init__(self, pinecone_index, namespace, modelo="text-embedding-ada-002", top_k=3, tentativas=3):
        self.pinecone_index = pinecone_index
        self.namespace = namespace
        self.modelo = modelo
        self.top_k = top_k
        self.tentativas = tentativas
        self.best_chunks = []

    async def buscar(self, query: str) -> List[str]:
        for tentativa in range(self.tentativas):
            try:
                embedding = openai.Embedding.create(
                    input=query,
                    model=self.modelo
                )["data"][0]["embedding"]

                results = self.pinecone_index.query(
                    vector=embedding,
                    top_k=self.top_k,
                    include_metadata=True,
                    namespace=self.namespace
                )

                self.best_chunks = [
                    " | ".join(f"{k}: {v}" for k, v in match.get("metadata", {}).items() if k != "id")
                    for match in results.get("matches", [])
                    if match.get("metadata")
                ]
                return self.best_chunks

            except Exception as e:
                logger.error(f"[BuscadorChunks] Tentativa {tentativa+1}: {e}")

        logger.critical("[BuscadorChunks] Falha ao buscar chunks após múltiplas tentativas.")
        self.best_chunks = []
        return []
