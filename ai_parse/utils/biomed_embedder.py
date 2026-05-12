import numpy as np
import torch
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
from config.backendSettings import PUBMEDBERT_EMBEDDING_PATH

class BiomedEmbedder:
    def __init__(self, model_path: str = None, device: str = None):
        model_path = model_path or PUBMEDBERT_EMBEDDING_PATH
        if device is None:
            device = "cuda" if torch.cuda.is_available() else "cpu"
        self.model = SentenceTransformer(model_path, device=device)

    # 返回二维 np.ndarray (n_texts, embedding_dim)
    def embed_batch(self, texts: list[str]) -> np.ndarray:
        if not texts:
            return np.zeros((0, self.model.get_sentence_embedding_dimension()), dtype=np.float32)
        embeddings = self.model.encode(
            texts,
            convert_to_numpy=True,
            normalize_embeddings=True
        ).astype(np.float32)
        if embeddings.ndim == 1:
            embeddings = embeddings.reshape(1, -1)
        return embeddings

    def similarity_between_embeddings(self, emb1: np.ndarray, emb2: np.ndarray) -> float:
        return float(cosine_similarity(emb1.reshape(1, -1), emb2.reshape(1, -1))[0][0])
