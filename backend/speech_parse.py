"""
Монголоор хэлсэн тоо, тийм/үгүй, нэрийг задлах (AI туслах, assistant.py).
STT-ийн түгээмэл алдааг тэвчинэ: "наян" -> "ноён", "далан хоёр долоон зуу" -> "72700".
"""
import re

DIGITS = ["тэг", "нэг", "хоёр", "гурав", "дөрөв", "тав", "зургаа", "долоо", "найм", "ес"]

YES = {"тийм", "за", "зөв", "мөн", "тиймээ", "болно", "болох", "тэгье", "тэгнэ", "зүгээр", "тиймэ"}
NO = {"үгүй", "биш", "буруу", "болохгүй", "хэрэггүй", "үгүйээ"}

UNITS = {"тэг": 0, "нэг": 1, "хоёр": 2, "гурав": 3, "гурван": 3, "дөрөв": 4, "дөрвөн": 4,
         "тав": 5, "таван": 5, "зургаа": 6, "зургаан": 6, "долоо": 7, "долоон": 7,
         "найм": 8, "найман": 8, "ес": 9, "есөн": 9}
TENS = {"арав": 10, "арван": 10, "хорь": 20, "хорин": 20, "гуч": 30, "гучин": 30, "дөч": 40,
        "дөчин": 40, "тавь": 50, "тавин": 50, "жар": 60, "жаран": 60, "дал": 70, "далан": 70,
        "ная": 80, "наян": 80, "ер": 90, "ерэн": 90}
HUNDRED = {"зуу", "зуун"}
# STT-ийн түгээмэл алдаа (бодит дуудлагаас): "наян" -> "ноён", "ноян", "оройн"
TENS.update({"ноён": 80, "ноян": 80, "оройн": 80, "наянн": 80})
# Аравтын араас ирсэн эдгээрийг нэгж гэж үзнэ: "наян тавь" (80, 50 биш) -> 85; "наян ер" -> 89
UNIT_AFTER_TENS = {"тавь": 5, "ер": 9}


def parse_phone(text: str) -> str:
    """Монголоор хэлсэн дугаарыг цифр болгоно: "далан хоёр долоон зуу найман зуу" -> "72700800",
    "наян найм ерэн нэг" -> "8891". STT цифрээр бичсэн бол шууд авна."""
    toks = re.findall(r"\d+|[а-яөүё]+", text.lower())
    out, i = "", 0

    def unit_free(j):          # toks[j] нь нэгж бөгөөд араас нь "зуу" ирээгүй (тэр нь шинэ бүлэг)
        return (j < len(toks) and toks[j] in UNITS
                and not (j + 1 < len(toks) and toks[j + 1] in HUNDRED))

    def tens_at(j):            # [TENS [UNIT]] -> (утга, дараагийн байрлал)
        if j < len(toks) and toks[j] in TENS:
            val = TENS[toks[j]]
            if j + 1 < len(toks) and toks[j + 1] in UNIT_AFTER_TENS:
                return val + UNIT_AFTER_TENS[toks[j + 1]], j + 2
            if unit_free(j + 1) and UNITS[toks[j + 1]] > 0:
                return val + UNITS[toks[j + 1]], j + 2
            return val, j + 1
        return None, j

    while i < len(toks):
        t = toks[i]
        if t.isdigit():
            out += t
            i += 1
        elif t in UNITS and i + 1 < len(toks) and toks[i + 1] in HUNDRED:
            val, j = UNITS[t] * 100, i + 2          # "долоон зуу", "долоон зуун тавь"
            rest, j2 = tens_at(j)
            if rest is not None:
                val, j = val + rest, j2
            elif unit_free(j):
                val, j = val + UNITS[toks[j]], j + 1
            out += f"{val:03d}"
            i = j
        elif t in TENS:
            val, i = tens_at(i)
            out += f"{val:02d}"
        elif t in UNITS:
            out += str(UNITS[t])
            i += 1
        else:
            i += 1
    if len(out) == 11 and out.startswith("976"):
        out = out[3:]
    return out


def clean_name(text: str) -> str:
    """"Миний нэр Батболд", "Намайг Батболд гэдэг" -> "Батболд"."""
    t = re.sub(r"[^\w\s-]", " ", text).strip()
    t = re.sub(r"^(миний\s+нэр(ийг)?|намайг|нэр\s+минь|би)\s+", "", t, flags=re.I)
    t = re.sub(r"\s+(гэдэг|гэнэ|гэж\s+хэлдэг|байна|байгаа)$", "", t, flags=re.I)
    return " ".join(w.capitalize() for w in t.split()) or text.strip()


def yes_no(text: str) -> bool | None:
    words = set(re.findall(r"[а-яөүё]+", text.lower()))
    if words & NO:
        return False
    if words & YES:
        return True
    return None
