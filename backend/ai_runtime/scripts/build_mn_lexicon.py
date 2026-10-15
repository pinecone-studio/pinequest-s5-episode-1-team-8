"""
Монгол үгсийн толь (data/mn_words.tsv) — mn_lexicon.Corrector STT-ийн алдааг засахад ашиглана.

  python scripts/build_mn_lexicon.py

Эх сурвалж: Leipzig Corpora Collection, монгол Википедиа 2021 (100K өгүүлбэр, CC BY 4.0)
https://wortschatz.uni-leipzig.de — үг бүрийн давтамжаар. Зөвхөн кирилл үг (давтамжийн хамт).
"""
import io
import os
import re
import sys
import tarfile
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from mn_lexicon import BASE_PATH  # noqa: E402

URL = "https://downloads.wortschatz-leipzig.de/corpora/mon_wikipedia_2021_100K.tar.gz"
WORD = re.compile(r"^[а-яөүё]+$")


def main():
    print(f"Татаж байна: {URL}")
    with urllib.request.urlopen(URL, timeout=120) as r:
        data = r.read()
    counts: dict[str, int] = {}
    with tarfile.open(fileobj=io.BytesIO(data)) as tar:
        member = next(m for m in tar.getmembers() if m.name.endswith("-words.txt"))
        for line in io.TextIOWrapper(tar.extractfile(member), encoding="utf-8"):
            parts = line.rstrip("\n").split("\t")
            if len(parts) != 3:
                continue
            word, freq = parts[1].lower(), int(parts[2])
            if WORD.match(word):
                counts[word] = counts.get(word, 0) + freq
    os.makedirs(os.path.dirname(BASE_PATH), exist_ok=True)
    with open(BASE_PATH, "w", encoding="utf-8") as f:
        for word, freq in sorted(counts.items(), key=lambda x: -x[1]):
            f.write(f"{word}\t{freq}\n")
    print(f"{len(counts)} үг -> {BASE_PATH}")


if __name__ == "__main__":
    main()
