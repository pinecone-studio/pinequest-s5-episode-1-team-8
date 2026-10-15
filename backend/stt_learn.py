"""
Ажилтны засвараас яриа таних (STT) алдааг өөрөө сурна.

«Хариулж чадаагүй асуулт» хуудсанд AI-ийн сонссон бичвэрийн ("цургалтын дээл хэд вэ") хажууд
зөв хувилбарыг ("сургалтын зээл хэд вэ") бичихэд үгсийг тулгаж, ялгаатай үгийг config.json
"stt_fixes"-д нэмнэ. AI сервер config өөрчлөгдөхөд өөрөө дахин ачаалж (FAQRouter.reload_if_changed),
дараагийн дуудлагаас ижил алдааг засна.
"""
import difflib
import re
import time

from tenant import Tenant

WORD = re.compile(r"[а-яөүёa-z]+", re.I)
MAX_WORDS = 2          # нэг засварт хамгийн ихдээ 2 үг ("пайн кун" -> "Pinecone")
MIN_SIMILAR = 0.5      # огт өөр үг (асуултаа өөрөөр бичсэн: "авъя" -> "авмаар байна") бол засвар биш
LATIN = re.compile(r"[a-z]", re.I)


def word_fixes(heard: str, correct: str) -> list[tuple[str, str]]:
    """Сонссон ба зөв бичвэрийн ялгаатай үгс -> [(сонссон, зөв)]."""
    a = [w.lower() for w in WORD.findall(heard)]
    b = [w.lower() for w in WORD.findall(correct)]
    if not a or not b or difflib.SequenceMatcher(None, a, b).ratio() < 0.3:
        return []                       # өөр асуулт (хувилбар) — засвар биш
    out = []
    for op, i1, i2, j1, j2 in difflib.SequenceMatcher(None, a, b).get_opcodes():
        if op != "replace" or i2 - i1 > MAX_WORDS or j2 - j1 > MAX_WORDS:
            continue
        old = " ".join(a[i1:i2])
        new = " ".join(WORD.findall(correct)[j1:j2])            # зөв хувилбарын бичлэг (Pinecone)
        if len(old.replace(" ", "")) < 3 or old == new:
            continue
        similar = (difflib.SequenceMatcher(None, old, new).ratio() >= MIN_SIMILAR
                   and abs(len(old) - len(new)) <= 3)
        brand = LATIN.search(new) and not LATIN.search(old)    # "пайн кун" -> "Pinecone" (галиглал)
        if similar or brand:
            out.append((old, new))
    return out


def learn(t: Tenant, heard: str, correct: str, source: str = "засвар") -> list[dict]:
    """Шинэ засваруудыг config.json-д нэмж буцаана (давхардуулахгүй)."""
    pairs = word_fixes(heard, correct)
    if not pairs:
        return []
    cfg = t.config()
    fixes = cfg.setdefault("stt_fixes", [])
    known = {(f.get("heard"), f.get("fix")) for f in fixes}
    added = []
    for old, new in pairs:
        pattern = r"\s?".join(re.escape(w) for w in old.split())   # "пайн кун" ~ "пайнкун"
        # Аль хэдийн засагддаг үг (өөр regex-д багтсан) эсвэл эсрэг засвар байвал нэмэхгүй
        if (pattern, new) in known or any(re.fullmatch(f.get("heard", "$^"), old, re.I)
                                          for f in fixes if _valid(f.get("heard"))):
            continue
        item = {"heard": pattern, "fix": new, "note": f"auto ({source}, {time.strftime('%m-%d')}): {old} -> {new}"}
        fixes.append(item)
        known.add((pattern, new))
        added.append(item)
    if added:
        t.save_config(cfg)
    return added


def _valid(pattern) -> bool:
    try:
        re.compile(pattern)
        return True
    except (re.error, TypeError):
        return False


def learn_existing(t: Tenant) -> list[dict]:
    """Өмнө нь «Хариулж чадаагүй асуулт»-аас бичсэн хариултуудын (faq.json source=web) асуулт ба
    ажилтны хувилбаруудаас нэг удаа сурна:  python -c "import stt_learn, tenant; ..."."""
    import json
    try:
        with open(t.faq_path, encoding="utf-8") as f:
            items = [x for x in json.load(f).get("faq", []) if x.get("source") == "web"]
    except (OSError, ValueError):
        return []
    return [x for item in items for v in item["questions"][1:]
            for x in learn(t, item["questions"][0], v, "өмнөх хариулт")]
