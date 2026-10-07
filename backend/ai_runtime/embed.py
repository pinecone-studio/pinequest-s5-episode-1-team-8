"""
Локал multilingual embedding (FAQ таних + RAG хайлт хоёуланд нэг модель).

  EMBED_MODEL=BAAI/bge-m3                      (default, монголд хамгийн сайн)
  EMBED_MODEL=intfloat/multilingual-e5-small   (жижиг, RAM бага)
"""
import offline  # noqa: F401  (хамгийн эхэнд: HF загварыг зөвхөн локалаас)
import os

import numpy as np

EMBED_MODEL = os.getenv("EMBED_MODEL", "BAAI/bge-m3")


class Embedder:
    def __init__(self, model: str = EMBED_MODEL):
        import torch
        from sentence_transformers import SentenceTransformer

        kwargs = {"torch_dtype": torch.float16} if "bge-m3" in model else {}
        self.model_name = model
        self.model = SentenceTransformer(model, model_kwargs=kwargs)
        # e5 модель "query: " / "passage: " угтвар шаарддаг
        self.e5 = "e5" in model

    def query(self, texts: list[str]) -> np.ndarray:
        if self.e5:
            texts = [f"query: {t}" for t in texts]
        return self.model.encode(texts, normalize_embeddings=True).astype(np.float32)

    def passage(self, texts: list[str]) -> np.ndarray:
        if self.e5:
            texts = [f"passage: {t}" for t in texts]
        return self.model.encode(texts, normalize_embeddings=True,
                                 show_progress_bar=len(texts) > 20).astype(np.float32)
