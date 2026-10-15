"""
Монгол толиор STT-ийн алдааг засна — LLM-гүй, хэдэн миллисекундэд (дуудлагыг удаашруулахгүй).

  1. Толинд байхгүй үг ("цургалт") -> 1 үсгийн зөрүүтэй байгууллагын үг ("сургалт").
     Зөвхөн байгууллагын үг (FAQ, мэдээлэл) рүү засна: Википедиагийн дурын үг рүү засахад
     "намин" -> "намын", "аягүй" -> "азгүй" гэж эвдэрч байсан (бодит дуудлагын туршилт).
     Монгол толь (Википедиа) нь зөв үгийг "алдаа" гэж андуурахгүйн тулд хэрэглэгдэнэ.
  2. Утгын алдаа: толинд байгаа ч энэ байгууллагад хамаагүй үг, хажуугийн үгтэйгээ хэзээ ч хамт
     ордоггүй ("сургалтын дээл") -> 1 үсгийн зөрүүтэй, байгууллагын бичвэрт хажуугийн үгтэй нь
     хамт ордог үг ("сургалтын зээл").

Монгол үгсийн толь: data/mn_words.tsv (scripts/build_mn_lexicon.py — Leipzig корпус, монгол Википедиа).
Файл байхгүй бол зөвхөн байгууллагын бичвэрээр ажиллана.
"""
import os
import re
from collections import Counter

import tenant

WORD = re.compile(r"[а-яөүё]+", re.I)
BASE_PATH = os.path.join(tenant.ROOT, "data", "mn_words.tsv")
MIN_LEN = 4                 # богино үг ("ба", "тэр") засвал утга эвдэрнэ
_base: dict[str, int] | None = None


def base_words() -> dict[str, int]:
    """үг -> давтамж (нэг удаа ачаална, бүх байгууллагад нийтлэг)."""
    global _base
    if _base is None:
        _base = {}
        if os.path.exists(BASE_PATH):
            with open(BASE_PATH, encoding="utf-8") as f:
                for line in f:
                    word, _, freq = line.rstrip("\n").partition("\t")
                    if word:
                        _base[word] = int(freq or 1)
    return _base


def words(text: str) -> list[str]:
    return [w.lower() for w in WORD.findall(text or "")]


def _deletes(word: str) -> set[str]:
    return {word[:i] + word[i + 1:] for i in range(len(word))}


def _dist1(a: str, b: str) -> bool:
    """Левенштейн зай <= 1 (солих, нэмэх, хасах)."""
    if a == b:
        return True
    if abs(len(a) - len(b)) > 1:
        return False
    if len(a) == len(b):
        return sum(x != y for x, y in zip(a, b)) == 1
    short, long_ = (a, b) if len(a) < len(b) else (b, a)
    return any(long_[:i] + long_[i + 1:] == short for i in range(len(long_)))


class Corrector:
    def __init__(self, domain_texts: list[str], extra_words: list[str] = (), known: list[str] = ()):
        base = base_words()
        domain = Counter()
        self.bigrams = Counter()
        for text in domain_texts:
            ws = words(text)
            domain.update(ws)
            self.bigrams.update(zip(ws, ws[1:]))
        for w in extra_words:
            domain.update(words(w))
        self.domain = set(domain)
        # known: хүний нэр гэх мэт — хэзээ ч засахгүй (нэрийг names.py тусад нь засна)
        self.valid = set(base) | self.domain | {w for k in known for w in words(k)}
        # нэр дэвшигч: зөвхөн байгууллагын үг (давтамж ихтэй нь эхэнд)
        score = {w: n * 1000 + base.get(w, 0) // 1000 for w, n in domain.items() if len(w) >= MIN_LEN}
        self.score = score
        self.index: dict[str, list[str]] = {}
        for w in score:
            for key in _deletes(w) | {w}:
                self.index.setdefault(key, []).append(w)

    def candidates(self, word: str) -> list[str]:
        found = set()
        for key in _deletes(word) | {word}:
            found.update(self.index.get(key, ()))
        return [c for c in found if c != word and _dist1(word, c)]

    def fix(self, text: str) -> tuple[str, list[tuple[str, str]]]:
        """-> (засварласан бичвэр, [(хуучин, шинэ)])"""
        tokens = WORD.findall(text)
        low = [t.lower() for t in tokens]
        changes = []
        for i, w in enumerate(low):
            if len(w) < MIN_LEN or w in self.domain:
                continue
            near = [x for x in (low[i - 1] if i else None, low[i + 1] if i + 1 < len(low) else None) if x]
            best = None
            if w not in self.valid:                       # 1. толинд байхгүй үг
                cands = self.candidates(w)
                if cands:
                    best = max(cands, key=lambda c: (self._ctx(c, i, low), self.score[c]))
            else:                                         # 2. утгын алдаа (хажуугийн үгтэй нийцэхгүй)
                if near and not any(self._pair(w, i, low)):
                    cands = [c for c in self.candidates(w) if c in self.domain and self._ctx(c, i, low) >= 1]
                    if cands:
                        best = max(cands, key=lambda c: (self._ctx(c, i, low), self.score[c]))
            if best:
                changes.append((tokens[i], best))
                low[i] = best
        for old, new in changes:
            text = re.sub(rf"(?<![а-яөүё]){re.escape(old)}(?![а-яөүё])", new, text, count=1, flags=re.I)
        return text, changes

    def _pair(self, w: str, i: int, low: list[str]):
        if i:
            yield self.bigrams[(low[i - 1], w)] > 0
        if i + 1 < len(low):
            yield self.bigrams[(w, low[i + 1])] > 0

    def _ctx(self, w: str, i: int, low: list[str]) -> int:
        """Байгууллагын бичвэрт хажуугийн үгтэй хамт орсон тоо."""
        n = self.bigrams[(low[i - 1], w)] if i else 0
        return n + (self.bigrams[(w, low[i + 1])] if i + 1 < len(low) else 0)
