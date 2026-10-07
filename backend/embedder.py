"""
RAG-ийн вектор (AI туслах — хувийн баримт, хүсэлт, сул цаг, байгууллагын мэдээллээс хайх).

  RAG_EMBED=char    (анхдагч) үсгийн 2-4 n-gram + үгийн язгуур -> 4096 хэмжээст вектор. Зөвхөн numpy, нэмэлт
                    сан/загвар татахгүй; STT-ийн үсгийн алдаа ("хөлбөр"), нөхцөл ("Болдын")-д тэсвэртэй.
  RAG_EMBED=bge-m3  утгын вектор (BAAI/bge-m3, 1024). sentence-transformers суулгасан байх шаардлагатай:
                    uv pip install --python .venv/bin/python sentence-transformers  (~1.2GB санах ой)
"""
import os
import re
import threading
import zlib

import numpy as np

MODEL = os.getenv("RAG_EMBED", "char")
DIM = 4096
_lock = threading.Lock()
_st = None


def name() -> str:
    return "BAAI/bge-m3" if MODEL == "bge-m3" else "char-ngram"


# Асуултын сул үгс: "Төлбөр хэд вэ"-д "вэ" нь "Утас хэд вэ"-тэй адилхан харагдуулахгүй
STOP = {"вэ", "бэ", "уу", "үү", "юу", "юү", "нь", "байна", "байгаа", "билээ", "бол", "ээ", "аа", "оо", "өө", "за", "л", "юм"}


def _char(texts: list[str]) -> np.ndarray:
    out = np.zeros((len(texts), DIM), np.float32)
    for i, text in enumerate(texts):
        words = re.findall(r"[а-яөүёa-z0-9]+", text.lower())
        for w in [x for x in words if x not in STOP] or words:
            padded = f" {w} "
            feats = [padded[j:j + n] for n in (2, 3, 4) for j in range(len(padded) - n + 1)]
            feats.append("§" + w[:4])                       # үгийн язгуур (нөхцөлгүй) илүү жинтэй
            for f in feats:
                out[i, zlib.crc32(f.encode()) % DIM] += 2.0 if f.startswith("§") else 1.0
    out = np.sqrt(out)                                       # олон давтагдсан n-gram давамгайлахгүй
    return out / np.maximum(np.linalg.norm(out, axis=1, keepdims=True), 1e-6)


def embed(texts: list[str]) -> np.ndarray:
    """-> normalized векторууд (cosine = dot)."""
    global _st
    if MODEL != "bge-m3":
        return _char(texts)
    with _lock:
        if _st is None:
            os.environ.setdefault("HF_HUB_OFFLINE", "1")
            from sentence_transformers import SentenceTransformer
            _st = SentenceTransformer("BAAI/bge-m3")
    return _st.encode(texts, normalize_embeddings=True).astype(np.float32)
