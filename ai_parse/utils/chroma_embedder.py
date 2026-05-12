from typing import List, Any
from chromadb import EmbeddingFunction
from .biomed_embedder import BiomedEmbedder
import numpy as np

class ChromaBiomedEmbeddingFunction(EmbeddingFunction):
    def __init__(self, model_path: str = None, device: str = None):
        self.embedder = BiomedEmbedder(model_path=model_path, device=device)

    # ChromaDB 会调用 __call__，必须返回 List[List[float]]
    def __call__(self, input: Any) -> List[List[float]]:
        if isinstance(input, str):
            texts = [input]
        elif isinstance(input, list):
            texts = [str(x) for x in input]
        else:
            texts = [str(input)]

        embeddings = self.embedder.embed_batch(texts)
        if embeddings.ndim == 1:
            embeddings = embeddings.reshape(1, -1)
        return embeddings.tolist()

    def embed_documents(self, input: List[str]) -> List[List[float]]:
        return self(input)
