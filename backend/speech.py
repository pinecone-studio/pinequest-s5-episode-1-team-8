"""
Тоог монгол үгээр (утсаар уншихад). FAQ-ийн хариултад утасны дугаарыг үгээр бичнэ:
  "72700800" -> "далан хоёр, долоон зуу, найман зуу",  "99112233" -> "ерэн ес, арван нэг, хорин хоёр, гучин гурав"
"""
import re

UNIT = ["тэг", "нэг", "хоёр", "гурав", "дөрөв", "тав", "зургаа", "долоо", "найм", "ес"]
UNIT_ATTR = ["тэг", "нэг", "хоёр", "гурван", "дөрвөн", "таван", "зургаан", "долоон", "найман", "есөн"]
TENS = ["", "арав", "хорь", "гуч", "дөч", "тавь", "жар", "дал", "ная", "ер"]
TENS_ATTR = ["", "арван", "хорин", "гучин", "дөчин", "тавин", "жаран", "далан", "наян", "ерэн"]


def below_1000(n: int, attr: bool) -> str:
    """0-999. attr=True: араас нь үг залгана ("таван сар"), False: дангаараа ("тав")."""
    if n == 0:
        return "тэг"
    h, rest = divmod(n, 100)
    t, u = divmod(rest, 10)
    words = []
    if h:
        last = not rest
        words += ([UNIT_ATTR[h]] if h > 1 else []) + ["зуу" if last and not attr else "зуун"]
    if t:
        words.append(TENS[t] if not u and not attr else TENS_ATTR[t])
    if u:
        words.append(UNIT_ATTR[u] if attr else UNIT[u])
    return " ".join(words)


def to_words(n: int, attr: bool = False) -> str:
    if n < 1000:
        return below_1000(n, attr)
    parts = []
    for value, word, word_attr in ((10**9, "тэрбум", "тэрбум"), (10**6, "сая", "сая"), (1000, "мянга", "мянган")):
        q, n = divmod(n, value)
        if q:
            last = n == 0
            parts.append(f"{below_1000(q, True)} {word if last and not attr else word_attr}")
    if n:
        parts.append(below_1000(n, attr))
    return " ".join(parts)


def pair(d: str) -> str:
    """Утасны дугаарын 2 оронтой хэсэг: "08" -> "тэг найм", "00" -> "тэг тэг", "70" -> "дал"."""
    if d[0] == "0":
        return f"тэг {UNIT[int(d[1])]}"
    return to_words(int(d))


def number_words(number: str, phone: bool = False) -> str:
    digits = re.sub(r"\D", "", number)
    if not phone:
        return to_words(int(digits)) if digits else ""
    if digits.startswith("976") and len(digits) == 11:
        digits = digits[3:]
    if len(digits) == 8 and re.fullmatch(r"\d{2}[1-9]00[1-9]00", digits):   # 72 700 800
        return ", ".join([pair(digits[:2]), to_words(int(digits[2:5])), to_words(int(digits[5:]))])
    groups = [digits[i:i + 2] for i in range(0, len(digits) - len(digits) % 2, 2)]
    words = [pair(g) for g in groups] + ([UNIT[int(digits[-1])]] if len(digits) % 2 else [])
    return ", ".join(words)
