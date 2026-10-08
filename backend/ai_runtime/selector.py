"""
Сургасан хариулт сонгогч: залгагчийн асуулт -> аль бэлэн аудиог тоглуулах вэ.

Бүхэлдээ локал, API-гүй. Хоёр төрлийн шинж:
  - bge-m3 embedding (утга) — FAQRouter аль хэдийн тооцоолсон векторыг дахин ашиглана (нэмэлт хугацаагүй)
  - үсгийн n-gram (2-4) + бүтэн үг — STT-ийн үсгийн алдаа ("хөлбөр", "сэд")-нд тэсвэртэй
Эдгээр дээр logistic regression сургана (scripts/train_selector.py). Ажиллахдаа зөвхөн numpy.

Шошго:
  faq:<id>        FAQ-ийн бэлэн хариулт
  fact:<hash>     knowledge-ийн нэг өгүүлбэр
  multi:<hash>    хэд хэдэн өгүүлбэр дараалан ("төлбөрийн нөхцөл" -> 3 нөхцөл бүгд)
  other           мэдээлэлд алга / хамааралгүй -> дахин асуух, ажилтан
  clarify         хэт ерөнхий асуулт -> тодруулна
"""
import hashlib
import json
import math
import os
import re
import zlib

import numpy as np

CHAR_DIM = 1 << 14
NGRAMS = (2, 3, 4)
FILES = ("selector.npz", "selector.json")


def normalize(text: str) -> str:
    text = text.lower().replace("ё", "е")
    return " ".join(re.sub(r"[^\w]+", " ", text).split())


def text_key(text: str) -> str:
    return hashlib.sha1(normalize(text).encode()).hexdigest()[:12]


def fact_label(text: str) -> str:
    return f"fact:{text_key(text)}"


def multi_label(texts: list[str]) -> str:
    return f"multi:{text_key('|'.join(texts))}"


def _buckets(text: str) -> dict[int, float]:
    counts: dict[int, float] = {}
    for word in normalize(text).split():
        grams = [f"w:{word}"]
        padded = f" {word} "
        for n in NGRAMS:
            grams += [padded[i:i + n] for i in range(len(padded) - n + 1)]
        for g in grams:
            b = zlib.crc32(g.encode()) % CHAR_DIM
            counts[b] = counts.get(b, 0.0) + 1.0
    return counts


def char_vector(text: str, idf: np.ndarray | None = None) -> tuple[np.ndarray, np.ndarray]:
    """Хэшлэсэн n-gram -> (индекс, утга), 1+log(tf) * idf, L2 нормчилсон."""
    counts = _buckets(text)
    if not counts:
        return np.zeros(0, np.int64), np.zeros(0, np.float32)
    idx = np.fromiter(counts.keys(), np.int64, len(counts))
    val = np.array([1.0 + math.log(c) for c in counts.values()], np.float32)
    if idf is not None:
        val *= idf[idx]
    val /= np.linalg.norm(val) or 1.0
    return idx, val


def char_matrix(texts: list[str], idf: np.ndarray | None = None):
    from scipy.sparse import csr_matrix
    rows, cols, vals = [], [], []
    for r, t in enumerate(texts):
        idx, val = char_vector(t, idf)
        rows += [r] * len(idx)
        cols += idx.tolist()
        vals += val.tolist()
    return csr_matrix((vals, (rows, cols)), shape=(len(texts), CHAR_DIM), dtype=np.float32)


def compute_idf(texts: list[str]) -> np.ndarray:
    df = np.zeros(CHAR_DIM, np.float32)
    for t in texts:
        for b in _buckets(t):
            df[b] += 1
    return (np.log((1 + len(texts)) / (1 + df)) + 1).astype(np.float32)


class Selector:
    def __init__(self, d: str):
        with open(os.path.join(d, "selector.json"), encoding="utf-8") as f:
            self.meta = json.load(f)
        z = np.load(os.path.join(d, "selector.npz"))
        self.W, self.b, self.idf = z["W"], z["b"], z["idf"]
        self.labels: list[str] = self.meta["labels"]
        if self.W.shape[0] != len(self.labels):     # сургалт файлуудыг солих зуур уншсан
            raise ValueError("selector.npz болон selector.json таарахгүй байна")
        self.answers: dict = self.meta["answers"]
        self.emb_w, self.char_w = self.meta["emb_w"], self.meta["char_w"]
        # Шалгалтаар дүрмээс муу гарвал ашиглахгүй (train_selector.py шийднэ)
        self.enabled = self.meta.get("enabled", True)

    def predict(self, text: str, vec: np.ndarray, k: int = 3) -> list[tuple[str, float]]:
        dim = len(vec)
        logits = (self.W[:, :dim] @ vec) * self.emb_w + self.b
        idx, val = char_vector(text, self.idf)
        if len(idx):
            logits = logits + (self.W[:, dim + idx] @ val) * self.char_w
        p = np.exp(logits - logits.max())
        p /= p.sum()
        top = np.argsort(-p)[:k]
        return [(self.labels[i], float(p[i])) for i in top]
