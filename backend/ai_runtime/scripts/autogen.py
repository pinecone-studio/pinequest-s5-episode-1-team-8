"""
Мэдээллээс бусад бүхнийг автоматаар бэлдэнэ (LLM, API-гүй, дүрэм/загвараар). Байгууллага зөвхөн
мэдээллээ (knowledge/) оруулахад AI ажиллах боломжтой болгох гол алхам.

  TENANT=<slug> .venv/bin/python scripts/autogen.py      # ingest.py --no-audio-ийн дараа

  1. Тодруулах сэдэв  : мэдээллийн "## Гарчиг"-уудаас (хамгийн олон өгүүлбэртэй 3)
  2. Ерөнхий үгс      : өгүүлбэрүүдийн 35%+-д давтагддаг үг (асуултыг ялгадаггүй -> тодруулах шалгуурт)
  3. Загвар FAQ       : мэндчилгээ, баярлалаа, ажилтан, бүртгэл, утас/хаяг/цаг (tenant.refresh_faq)
  4. Сургалтын асуулт : өгүүлбэр бүрээс түлхүүр үг + асуултын хэлбэр ("зээлийн хугацаа хэд вэ")
                        -> training/auto.json. Гарчгийн асуулт ("төлбөрийн нөхцөл") -> гарчгийн өгүүлбэрүүд
  5. Шалгалт          : асуултын нэг хэсгийг сургалтад оруулахгүй + STT-маягийн алдаа -> tests/auto_eval.json

Хязгаар: загвараар үүсгэсэн асуулт хүний бичсэнээс жигд, шалгалт нь өөрөө үүсгэсэн тул бодит чанарыг
дуудлагын дараа "Заах"-аар сайжруулна. Гараар тохируулсан утга (clarify_custom, eval_questions.json) хүндэтгэнэ.
"""
import json
import math
import os
import random
import re
import sys
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import tenant as tenants  # noqa: E402
from stream_voice import LEX_STOP, lex_stems  # noqa: E402

T = tenants.current()
STOP = LEX_STOP | {"бол", "гэх", "мэт", "зэрэг", "бүр", "нийт", "дээр", "үед", "тул", "бөгөөд", "болон", "ба",
                   "мөн", "манай", "танай", "тань", "өөрийн", "хийнэ", "авна", "өгнө", "байх", "болох", "нэг",
                   "хоёр", "гурав", "гурван", "дөрөв", "тав", "таван", "арав", "арван", "зуу", "зуун", "мянга",
                   "гаруй", "хүртэл", "эсвэл", "шиг", "юм", "нь", "уу", "үү", "аас", "ээс", "оос", "өөс"}
NUMBER = re.compile(r"\d|\b(нэг|хоёр|гурав|гурван|дөрөв|дөрвөн|тав|таван|зургаа|зургаан|долоо|долоон|найм|"
                    r"найман|ес|есөн|арав|арван|хорь|хорин|гуч|гучин|дөч|дөчин|тавь|тавин|жар|жаран|дал|далан|"
                    r"ная|наян|ер|ерэн|зуу|зуун|мянга|мянган|сая)\b")
# Хамааралгүй асуулт (бүх салбарт "мэдээлэлд алга"). Байгууллагын мэдээлэлтэй давхцвал хасна.
OTHER = ["маргааш бороо орох уу", "өнөөдөр цаг агаар ямар байна", "өнөөдөр хэдэн бэ", "долларын ханш хэд байна",
         "такси дуудаж өгөөч", "хоол захиалах гэсэн юм", "уучлаарай буруу залгачихлаа", "сонсогдож байна уу",
         "аан ммм тэгээд", "чи хэдэн настай вэ", "нэг дуу дуулаад өгөөч", "инээдтэй юм яриад өгөөч",
         "пицца хэдэн төгрөг вэ", "автобус хэдэн цагт ирэх вэ", "цүнх мартчихсан байна", "миний найз байна уу",
         "футболын тоглолт хэд хэдээр дууссан бэ", "кино хэдэн цагт гарах вэ", "нисэх онгоцны билет хэд вэ",
         "эмийн сан хаана байна", "хамгийн ойр бензин колонк хаана вэ", "би хаана байна"]


def words(text: str) -> list[str]:
    return re.findall(r"[а-яөүёa-z]+", text.lower())


# Үйл үгийн төгсгөл ("үзүүлдэг", "хийнэ", "авсан", "төлж") -> түлхүүр үг биш (асуултын хэлбэр нь tails()-аас).
# "-х" (цайруулах, захиалах) нь нэр үг шиг сэдэв болдог тул үлдээнэ.
VERB = re.compile(r"(даг|дэг|дог|дөг|на|нэ|но|нө|сан|сэн|сон|сөн|лаа|лээ|лоо|лөө|ж|ч|аарай|ээрэй|уу|үү)$")
WEAK = {"урд", "талд", "тал", "хойд", "дээр", "доор", "өмнө", "дараа", "бий", "үгүй", "өдөр", "гарагт", "эмнэлэг"}


def keywords(fact: str, idf: dict[str, float], k: int = 4) -> list[str]:
    """Өгүүлбэрийг бусдаас ялгах нэр үгс: ховор язгуур эхэнд (тэнцвэл урт үг), язгуур давхардахгүй,
    анхны дараалал, хэлбэрээр нь."""
    cand, seen = [], []
    for i, w in enumerate(words(fact)):
        if len(w) < 3 or w in STOP or w in WEAK or NUMBER.fullmatch(w) or (not w.isascii() and VERB.search(w)):
            continue
        st = stem(w)
        if any(st.startswith(x[:3]) or x.startswith(st[:3]) for x in seen):
            continue
        seen.append(st)
        cand.append((i, w))
    best = sorted(cand, key=lambda x: (-idf.get(stem(x[1]), 0), -len(x[1])))[:k]
    return [w for _, w in sorted(best)]


def questions(fact: str, idf: dict[str, float]) -> list[str]:
    """Гол үгсийн хослол x асуултын хэлбэр: "суулгац хэд вэ", "шүдний суулгац хэдэн төгрөг вэ"."""
    kws, t = keywords(fact, idf), tails(fact)
    if not kws:
        return []
    qs = [f"{kw} {t[0]}" for kw in kws[:3]] + [f"{kws[0]} {x}" for x in t[1:3]]
    qs += [f"{a} {b} {t[0]}" for i, a in enumerate(kws[:3]) for b in kws[i + 1:3]]
    qs.append(f"{' '.join(kws[:2])} {t[-1]}")
    return list(dict.fromkeys(qs))[:8]


def stem(w: str) -> str:
    return w if w.isascii() else w[:4]


def tails(fact: str) -> list[str]:
    """Өгүүлбэрийн агуулгаас асуултын төгсгөл."""
    f = fact.lower()
    out = []
    if re.search(r"төгрөг|үнэ|төлбөр", f) and NUMBER.search(f):
        out += ["хэд вэ", "хэдэн төгрөг вэ"]
    if "хувь" in f:
        out += ["хэдэн хувь вэ"]
    if re.search(r"\b(сар|жил|долоо хоног|хоног|цаг|минут)", f) and NUMBER.search(f):
        out += ["хэр удаан бэ", "хэд вэ"]
    if re.search(r"хаяг|байрлад|давхар|дүүрэг|хороо|гудамж|байранд", f):
        out += ["хаана байдаг вэ"]
    if re.search(r"боломжтой|болно\b|болох\b", f):
        out += ["боломжтой юу", "болох уу"]
    if re.search(r"(дог|даг|дөг|дэг)\b", f):
        out += ["байдаг уу"]
    if NUMBER.search(f) and not out:
        out += ["хэд вэ"]
    return out + ["ямар вэ", "талаар мэдмээр байна"]


def main():
    facts_file = os.path.join(T.kb_index_dir, "facts.json")
    if not os.path.exists(facts_file):
        sys.exit("facts.json алга -> эхлээд scripts/ingest.py --no-audio")
    facts = json.load(open(facts_file, encoding="utf-8"))["facts"]
    cfg = T.config()
    rng = random.Random(11)
    print(f"{cfg.get('name', T.slug)}: {len(facts)} өгүүлбэр")

    # 1. тодруулах сэдэв (гарчгаас)
    sections = Counter(f["section"] for f in facts if f.get("section"))
    if not cfg.get("clarify_custom"):
        top = [s for s, _ in sections.most_common(3)]
        cfg["clarify_topics"] = [{"label": s[:1].lower() + s[1:], "keys": sorted(lex_stems(s)), "question": s}
                                 for s in top]
        print(f"  тодруулах сэдэв: {[t['label'] for t in cfg['clarify_topics']] or '— (## гарчиг алга)'}")

    # 2. ерөнхий үгс: өгүүлбэрүүдийн ихэнхэд байдаг (жишээ нь "сургалт" Pinecone-д)
    df = Counter(st for f in facts for st in lex_stems(f["text"]))
    n = max(len(facts), 1)
    cfg["generic_auto"] = sorted(st for st, c in df.items() if c / n >= 0.35 and n >= 6)
    print(f"  ерөнхий үгс: {cfg['generic_auto']}")
    T.save_config(cfg)

    # 3. загвар FAQ (сэдэвтэй мэндчилгээ гэх мэт)
    tenants.refresh_faq(T)

    # 4-5. асуулт үүсгэх
    idf = {st: math.log((1 + n) / (1 + c)) + 1 for st, c in df.items()}
    train, evals = [], []
    for f in facts:
        qs = questions(f["text"], idf)
        if not qs:
            continue
        rng.shuffle(qs)
        held = qs[0] if len(qs) >= 3 else None       # 1-ийг нь шалгалтад (сургалтад оруулахгүй)
        train += [{"q": q, "fact": f["text"], "source": "auto"} for q in qs if q != held]
        if held:
            evals.append({"q": held, "expect": f["text"][:30], "note": "автомат"})

    for sec, count in sections.items():                 # "Төлбөрийн нөхцөл" -> тэр гарчгийн өгүүлбэрүүд
        texts = [f["text"] for f in facts if f.get("section") == sec][:3]
        label = sec[:1].lower() + sec[1:]
        qs = [label, f"{label} ямар вэ", f"{label} талаар мэдмээр байна", f"{label} талаар асуух гэсэн юм"]
        train += [{"q": q, "facts": texts, "source": "auto"} for q in qs[1:]]
        evals.append({"q": qs[0], "expect": texts[0][:30], "note": "автомат: гарчиг"})

    domain = set(df)
    others = [q for q in OTHER if not (lex_stems(q) & domain)]
    rng.shuffle(others)
    cut = max(len(others) // 4, 1)
    train += [{"q": q, "label": "other", "source": "auto"} for q in others[cut:]]
    evals += [{"q": q, "expect": "REPEAT", "note": "автомат: хамааралгүй"} for q in others[:cut]]

    os.makedirs(os.path.dirname(T.auto_training_path), exist_ok=True)
    with open(T.auto_training_path, "w", encoding="utf-8") as fh:
        json.dump({"_note": "scripts/autogen.py үүсгэсэн (гараар бүү зас: дахин бэлдэхэд дарагдана). "
                            "Гараар нэмэх бол training/examples.json.",
                   "examples": train}, fh, ensure_ascii=False, indent=1)
    if not os.path.exists(T.eval_path):                 # гараар бичсэн шалгалт байвал түүнийг хэрэглэнэ
        os.makedirs(os.path.dirname(T.auto_eval_path), exist_ok=True)
        with open(T.auto_eval_path, "w", encoding="utf-8") as fh:
            json.dump({"_note": "scripts/autogen.py: сургалтад ороогүй асуултууд (өөрөө үүсгэсэн тул бодит "
                                "чанараас өөдрөг байж болно)", "questions": evals}, fh, ensure_ascii=False, indent=1)
    print(f"  сургалтын асуулт: {len(train)}, шалгалт: {len(evals)}"
          f"{' (гараар бичсэн шалгалт байгаа тул ашиглахгүй)' if os.path.exists(T.eval_path) else ''}")
    for ex in train[:6]:
        print(f"    жишээ: {ex['q']!r}")


if __name__ == "__main__":
    main()
