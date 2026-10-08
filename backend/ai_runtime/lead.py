"""
Lead бүртгэл + ажилтанд шилжүүлэх (олон алхамтай яриа).

Бүх асуулт урьдчилан бэлдсэн аудио (build_faq_audio.py) -> дуудлагын үеэр TTS ажиллахгүй.
Дугаарыг тоо бүрийн бэлэн аудиогоор буцааж уншиж баталгаажуулна. Дугаарыг таахгүй:
таниагүй бол дахин асууна, дараа нь "дугаар авч чадсангүй" гэж бүртгэнэ.

  Эхлэх 3 зам:
    "Бүртгүүлмээр байна"   (FAQ register)       -> нэр асууна
    "Ажилтантай ярья"     (FAQ human_request)  -> нэр асууна
    Мэдээлэл олдсонгүй    (error хэллэг)       -> "эргэж холбогдох уу?" -> тийм -> нэр
"""
import re

# Бүртгэлийн хэллэгүүд: байгууллага бүрийн config-оос (tenant.Tenant.phrases()["lead"]).
# Энд түлхүүрүүд л хэрэгтэй (LeadFlow.handle эдгээрийг буцаана).
from tenant import DEFAULT_PHRASES  # noqa: E402

PROMPTS = DEFAULT_PHRASES["lead"]
DIGITS = ["тэг", "нэг", "хоёр", "гурав", "дөрөв", "тав", "зургаа", "долоо", "найм", "ес"]

# Эдгээр FAQ хариултын дараа нэр асуух алхам эхэлнэ (хариулт нь өөрөө нэр асуудаг)
START_FAQ = {"register": "lead", "human_request": "handoff"}

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


def phone_from_caller(caller: str | None) -> str | None:
    """SIP trunk-ээр бодит дугаар ирвэл (Caller ID) түүнийг санал болгоно."""
    digits = re.sub(r"\D", "", caller or "")
    if len(digits) == 11 and digits.startswith("976"):
        digits = digits[3:]
    return digits if len(digits) == 8 else None


class LeadFlow:
    """Нэг дуудлагын бүртгэлийн яриа. handle(text) -> тоглуулах клипүүд, дууссан эсэх."""

    def __init__(self, reason: str, state: str, caller: str | None, lang: str = "mn"):
        self.lang = lang              # "mn" | "en" (english.py-ийн хэллэг, задлагч)
        self.reason = reason          # "lead" | "handoff"
        self.state = state            # offer | name | phone | confirm
        self.caller = caller
        self.name = None
        self.phone = None
        self.phone_raw = []
        self.phone_tries = 0
        self.result = None            # "saved" | "saved_no_phone" | "declined"

    def _yes_no(self, text: str) -> bool | None:
        if self.lang == "en":
            from english import yes_no_en
            return yes_no_en(text)
        return yes_no(text)

    def _name(self, text: str) -> str:
        if self.lang == "en":
            from english import clean_name_en
            return clean_name_en(text)
        return clean_name(text)

    def _phone(self, text: str) -> str:
        if self.lang == "en":
            from english import parse_phone_en
            return parse_phone_en(text) or parse_phone(text)
        return parse_phone(text)

    def handle(self, text: str) -> list[str]:
        """Буцаах: тоглуулах prompt түлхүүрүүд ("digits:72700800" = дугаарыг уншина)."""
        if self.state == "offer":
            ans = self._yes_no(text)
            if ans is False:
                self.result = "declined"
                return ["declined"]
            if ans is None:
                # "тийм/үгүй" биш бол шинэ асуулт гэж үзээд яриаг энгийн горимд буцаана
                self.result = "declined"
                return []
            self.state = "name"
            return ["ask_name_again"]

        if self.state == "name":
            self.name = self._name(text)
            suggested = phone_from_caller(self.caller)
            if suggested:
                self.phone, self.state = suggested, "confirm"
                return ["readback", f"digits:{suggested}", "confirm"]
            self.state = "phone"
            return ["ask_phone"]

        if self.state == "phone":
            self.phone_raw.append(text)
            digits = self._phone(text)
            if len(digits) == 11 and digits.startswith("976"):
                digits = digits[3:]
            if len(digits) == 8:
                self.phone, self.state = digits, "confirm"
                return ["readback", f"digits:{digits}", "confirm"]
            self.phone_tries += 1
            if self.phone_tries >= 2:
                self.result = "saved_no_phone"
                return ["done_no_phone"]
            return ["phone_retry"]

        if self.state == "confirm":
            ans = self._yes_no(text)
            if ans is True:
                self.result = "saved"
                return ["done"]
            self.phone = None
            self.phone_tries += 1
            if self.phone_tries >= 3:
                self.result = "saved_no_phone"
                return ["done_no_phone"]
            self.state = "phone"
            return ["phone_retry"]
        return []

    @property
    def finished(self) -> bool:
        return self.result is not None
