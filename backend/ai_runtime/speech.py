"""
Бичгийн текстийг утсаар уншихад бэлдэх (TTS-ийн өмнө). Мэдээллийг хэрэглэгч цифрээр бичсэн ч
зөв уншина:  "72700800" -> "далан хоёр, дал, тэг найм, тэг тэг",  "09:00-18:00" -> "есөн цагаас
арван найман цаг хүртэл". Бусад тоог (5%, 1,500,000 төгрөг, 9-18 сар) Oron TTS-ийн normalizer уншдаг.
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


PHONE = re.compile(r"(?<![\d.,])(?:\+?976[\s-]?)?(\d{4})[\s-]?(\d{4})(?!\d|[.,]\d|%)")   # 8 орон (бутархай биш)
# "09:00-20:00 цагт" -> "есөн цагаас хорин цаг хүртэл" (араас нь "цагт" давхардуулахгүй)
TIME = re.compile(r"\b(\d{1,2}):(\d{2})\b(?:\s*(цагт|цагаас|цаг)\b)?")
TIME_RANGE = re.compile(r"\b(\d{1,2}):(\d{2})\s*[-–]\s*(\d{1,2}):(\d{2})\b(?:\s*цаг(?:т|ийн)?\b)?")


def clock(h: str, m: str) -> str:
    out = f"{to_words(int(h), attr=True)} цаг"
    return out + (f" {to_words(int(m), attr=True)} минут" if int(m) else "")


def time_words(m) -> str:
    """"09:00 цагт" -> "есөн цагт", "18:30 цагт" -> "арван найман цаг гучин минутад"."""
    hour, minute, suffix = m[1], m[2], m[3]
    if not suffix or suffix == "цаг":
        return clock(hour, minute)
    if not int(minute):
        return f"{to_words(int(hour), attr=True)} {suffix}"
    return clock(hour, minute) + {"цагт": "ад", "цагаас": "аас"}[suffix]


def speak(text: str) -> str:
    """TTS-ийн өмнө: утасны дугаар, цаг. Бусдыг хэвээр (Oron normalizer уншина)."""
    text = TIME_RANGE.sub(lambda m: f"{clock(m[1], m[2])}аас {clock(m[3], m[4])} хүртэл", text)
    text = TIME.sub(time_words, text)
    return PHONE.sub(lambda m: number_words(m[1] + m[2], phone=True), text)


def fallback(text: str) -> str:
    """Oron normalizer нөхцөлтэй тоонд ("5-нд") алдаа заавал: тоог үгээр, нөхцлийг хасна."""
    text = re.sub(r"(\d+)-[а-яөүё]+", lambda m: to_words(int(m[1])), text)
    return re.sub(r"\d+", lambda m: to_words(int(m[0])), text)


def apply_lexicon(text: str, lexicon: list[dict] | None) -> str:
    """Байгууллагын дуудлагын толь: [{"word": "МУИС", "say": "эм у и эс"}, {"word": "QPay", "say": "Q Pay"}].
    Бүтэн үгээр (нөхцөл залгасан ч: "QPay-ээр" -> "Q Pay-ээр"). "say" латин бол англиар, кирилл бол монголоор уншина."""
    for item in lexicon or []:
        word, say = (item.get("word") or "").strip(), (item.get("say") or "").strip()
        if word and say:
            text = re.sub(rf"(?<!\w){re.escape(word)}(?!\w)", say, text)
    return text
