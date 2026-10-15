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
from speech_parse import clean_name

# Бүртгэлийн хэллэгүүд: байгууллага бүрийн config-оос (tenant.Tenant.phrases()["lead"]).
# Энд түлхүүрүүд л хэрэгтэй (LeadFlow.handle эдгээрийг буцаана).
from tenant import DEFAULT_PHRASES  # noqa: E402

PROMPTS = DEFAULT_PHRASES["lead"]
DIGITS = ["тэг", "нэг", "хоёр", "гурав", "дөрөв", "тав", "зургаа", "долоо", "найм", "ес"]
# Дугаарыг хоёр хоёр оронгоор уншина ("85" -> "наян тав", "20" -> "хорь", "08" -> "тэг найм")
PAIR_TENS = ["", "арав", "хорь", "гуч", "дөч", "тавь", "жар", "дал", "ная", "ер"]
PAIR_TENS_ATTR = ["", "арван", "хорин", "гучин", "дөчин", "тавин", "жаран", "далан", "наян", "ерэн"]
PAIRS = [f"{i:02d}" for i in range(100)]


def pair_word(pair: str) -> str:
    tens, unit = int(pair[0]), int(pair[1])
    if tens == 0:
        return f"{DIGITS[0]} {DIGITS[unit]}"
    return PAIR_TENS[tens] if unit == 0 else f"{PAIR_TENS_ATTR[tens]} {DIGITS[unit]}"

# Эдгээр FAQ хариултын дараа нэр асуух алхам эхэлнэ (хариулт нь өөрөө нэр асуудаг)
START_FAQ = {"register": "lead", "human_request": "handoff"}

# Товчлуургүйгээр яриагаар тийм/үгүй (товчлуур зөвхөн утасны дугаар, 4 оронтой кодод)
YES = {"тийм", "за", "зөв", "мөн", "тиймээ", "болно", "болох", "тэгье", "тэгнэ", "зүгээр", "тиймэ",
       "очно", "очъё", "очье", "ирнэ", "ирье", "ирэх", "очих", "мэдээж", "тэгээрэй", "тэгэх", "зөвшөөрнө",
       "бүртгүүлнэ", "бүртгээрэй", "бүртгэ", "хүсэж", "хүснэ", "аваарай", "тэгээч", "ок", "okay", "yes"}
NO = {"үгүй", "биш", "буруу", "болохгүй", "хэрэггүй", "үгүйээ", "битгий", "боль", "больё", "болъё",
      "амжихгүй", "чадахгүй", "очихгүй", "ирэхгүй", "хүсэхгүй", "дараа", "no"}
UNSURE = {"мэдэхгүй", "ойлгохгүй", "ойлгосонгүй", "сонсогдохгүй", "сонсогдсонгүй", "санахгүй", "мэдэхгүйээ"}
# Зөвхөн дугаар баталгаажуулах үед: "зөв" -> STT "төв", "зөвөө" (бодит дуудлагаас)
CONFIRM_YES = re.compile(r"\b(зөв\w*|төв|дөв|зөвөө|төвөө)\b")

UNITS = {"тэг": 0, "нэг": 1, "хоёр": 2, "гурав": 3, "гурван": 3, "дөрөв": 4, "дөрвөн": 4,
         "тав": 5, "таван": 5, "зургаа": 6, "зургаан": 6, "долоо": 7, "долоон": 7,
         "найм": 8, "найман": 8, "ес": 9, "есөн": 9}
TENS = {"арав": 10, "арван": 10, "хорь": 20, "хорин": 20, "гуч": 30, "гучин": 30, "дөч": 40,
        "дөчин": 40, "тавь": 50, "тавин": 50, "жар": 60, "жаран": 60, "дал": 70, "далан": 70,
        "ная": 80, "наян": 80, "ер": 90, "ерэн": 90}
HUNDRED = {"зуу", "зуун"}
# STT-ийн түгээмэл алдаа (бодит дуудлагаас): "наян" -> "ноён", "ноян", "оройн"
TENS.update({"ноён": 80, "ноян": 80, "оройн": 80, "наянн": 80})
UNITS.update({"дургай": 6, "дургаа": 6, "зургай": 6, "зурга": 6})      # 10-15: "хорин дургай" (= 26)
# Аравтын араас ирсэн эдгээрийг нэгж гэж үзнэ: "наян тавь" (80, 50 биш) -> 85; "наян ер" -> 89
UNIT_AFTER_TENS = {"тавь": 5, "ер": 9}


# ---------------- Эвентийн бүртгэл ----------------
# "Хакатонд бүртгүүлмээр байна" (эвент) ба "Бүртгүүлмээр байна" (хөтөлбөр) өөр. Эвентийн үг эсвэл эвентийн нэр +
# оролцох үйл үг -> эвент. "Хакатоны талаар" (мэдээлэл) FAQ-д үлдэнэ, "эвентийн бүртгэлээ цуцлах" бүртгэл биш.
# STT "эвент"-ийг "эвээнт", "ивэнт", "эвэнд" гэж бичдэг (бодит туршилт)
# 10-15 туршилт: "эвээн түртгэлдсэн", "ивээн тэтгэвэрт гүйлмээр байна" (= эвентэд бүртгүүлмээр байна)
EVENT_RE = re.compile(r"[эи]в[эеи]*н(?:[тд]|\b)|юм[эе]н[дт]|event|арга хэмжээ|х[аэ]кк?[аэ]тон|hackathon|уралдаан|семинар")
JOIN_WORDS = ("бүртг", "бүтгүү", "бүрдүүл", "оролц", "очмоор", "очъё", "явмаар", "суумаар", "ирмээр", "хамрагд",
              "түртг", "гүйлмээр", "тэтгэв")   # 10-15: "эвээн тэтгэвэл/тэтгэвэрт" = эвентэд бүртгүүл
# Эвентийн үгтэй хамт "-маар/-мээр байна" (STT үйл үгийг эвдсэн ч хүсэлт хэвээр) -> бүртгүүлэх.
# Мэдээлэл асуух үйл үг ("мэдмээр", "сонсмоор", "асуумаар", "авмаар") бол бүртгэл биш.
DESIRE = re.compile(r"([а-яөүё]+)(?:мээр|маар|моор|мөөр)\b")
INFO_VERBS = ("мэд", "сонс", "асуу", "ав", "үз", "ойлго")
PROGRAM_WORDS = ("хөтөлбөр", "сургалт", "bootcamp", "буткэмп", "хичээл", "курс", "элс")
NOT_JOIN = ("цуца", "цуцл", "болих", "больё", "болъё", "гармаар", "хасуул", "чадахгүй", "өөрчл", "солих", "солимоор",
            "шалга", "хэзээ", "хаана")
EVENT_GENERIC = {"эвен", "ивен", "арга", "хэмж", "хэмжээ"}
QUESTION = re.compile(r"\b(хаана|хэзээ|хэдэн|хэд|ямар|юу|вэ|бэ)\b")
ORDINAL_WORDS = {"нэг": 0, "эхн": 0, "хоёр": 1, "гура": 2, "гурв": 2, "сүүл": -1}
_LAT = [("sh", "ш"), ("ch", "ч"), ("kh", "х"), ("ts", "ц"), ("ck", "к"), ("ph", "ф"), ("th", "т"), ("qu", "кв"),
        ("x", "кс")] + list(zip("abcdefghijklmnopqrstuvwyz", "абкдэфгхижклмнопкрстуввйз"))


def _cyr(word: str) -> str:
    """Латин эвентийн нэр -> кирилл (STT кириллээр бичдэг): "hackathon" -> "хакатон"."""
    for a, b in _LAT:
        word = word.replace(a, b)
    return word


def _words(text: str) -> list[str]:
    return [_cyr(w).replace("е", "э") for w in re.findall(r"[a-zа-яөүё]+", text.lower()) if len(w) >= 3]


def _close(a: str, b: str) -> bool:
    """Ижил үг (STT эгшгийг андуурдаг: "пайн" ~ "пин", "демо" ~ "дэмо")."""
    from names import _lev
    a, b = a[:6], b[:6]
    return a[:4] == b[:4] or _lev(a, b, 2) <= max(1, min(len(a), len(b)) // 3)


def match_event(text: str, events: list[dict]) -> dict | None:
    """Залгагч нэрлэсэн эвент ("хакатонд", "пайнквест демо") -> эвент (нэрийн үгсийн тал нь таарвал)."""
    said, best, score = _words(text), None, 0.0
    for e in events:
        words = [w for w in _words(e["name"]) if w[:4] not in EVENT_GENERIC]
        if words:
            hit = sum(any(_close(a, b) for a in said) for b in words) / len(words)
            if hit > score:
                best, score = e, hit
    return best if score >= 0.33 else None     # 3 үгтэй нэрийн 1 нь ("демо") хангалттай


def wants_register(text: str) -> bool:
    """Юунд гэдгийг хэлээгүй ерөнхий "бүртгүүлмээр байна" (эвент ч, хөтөлбөр ч биш)."""
    t = text.lower()
    return (any(w in t for w in JOIN_WORDS) and not any(w in t for w in NOT_JOIN)
            and not EVENT_RE.search(t) and not any(w in t for w in PROGRAM_WORDS))


def wants_event(text: str, events: list[dict]) -> bool:
    t = text.lower()
    desire = any(not m.group(1).startswith(INFO_VERBS) for m in DESIRE.finditer(t))
    if any(w in t for w in NOT_JOIN) or not (any(w in t for w in JOIN_WORDS) or desire):
        return False
    return bool(EVENT_RE.search(t)) or match_event(text, events) is not None


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


def yes_no(text: str) -> bool | None:
    digits = re.sub(r"\D", "", text or "")
    if digits == "1":
        return True
    if digits == "2":
        return False
    words = set(re.findall(r"[а-яөүёa-z]+", text.lower()))
    if words & UNSURE or QUESTION.search(text.lower()):
        return None                   # "мэдэхгүй", "хэдэн цагт болох вэ" — хариулт биш, дахин асууна
    # "очихгүй", "амжихгүй", "бүртгүүлэхгүй" — -хгүй нөхцөлтэй үйл үг бүгд үгүй
    if words & NO or any(w.endswith("хгүй") for w in words):
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

    def __init__(self, reason: str, state: str, caller: str | None, lang: str = "mn",
                 events: list[dict] | None = None, book: bool = False):
        self.lang = lang              # "mn" | "en" (english.py-ийн хэллэг, задлагч)
        self.reason = reason          # "lead" | "handoff" | "event"
        self.state = state            # event_start | event_pick | event_offer | offer | name | phone | confirm
        self.events = (events or [])[:3]   # удахгүй болох эвентүүд (ойроос нь)
        self.event: dict | None = None
        self.pick_tries = 0
        self.book = book              # бүртгэлийн дараа "Уулзалтын цаг товлох уу?" (сул цаг байвал)
        self.save_pending = False     # дугаар баталгаажсан -> phone_server одоо хадгална (урсгал үргэлжилнэ)
        self.saved = False            # phone_server хадгалсан (давхар хадгалахгүй)
        self.duplicate = False        # энэ хөтөлбөр/эвентэд аль хэдийн бүртгэлтэй (phone_server тогтооно)
        self.caller = caller
        self.name = None
        self.phone = None
        self.phone_raw = []
        self.phone_tries = 0
        self.confirm_tries = 0
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

    def _offer_event(self, ev: dict) -> list[str]:
        self.event, self.state = ev, "event_offer"
        return [f"ev:{ev['name']}", f"date:{ev['at']}", "event_ask"]

    def _pick_event(self, text: str) -> dict | None:
        digits = re.sub(r"\D", "", text)
        if len(digits) == 1 and 1 <= int(digits) <= len(self.events):
            return self.events[int(digits) - 1]
        for w in re.findall(r"[а-яөүё]+", text.lower()):
            i = ORDINAL_WORDS.get(w[:4], ORDINAL_WORDS.get(w[:3]))
            if i is not None and i < len(self.events):
                return self.events[i]
        return match_event(text, self.events)

    def handle(self, text: str) -> list[str]:
        """Буцаах: тоглуулах prompt түлхүүрүүд ("digits:72700800" = дугаарыг уншина,
        "ev:<нэр>" = эвентийн нэр, "date:2026-10-18T10:00" = гараг сар өдөр цаг)."""
        if self.state == "which_start":
            self.state = "which"
            return ["which_ask"]
        if self.state == "which":         # "Хөтөлбөрт үү, арга хэмжээнд үү?"
            t = text.lower()
            if EVENT_RE.search(t) or match_event(text, self.events) or "хоёрд" in t or "сүүлийн" in t:
                self.reason, self.state, self.book = "event", "event_start", False
                return self.handle(text)
            if any(w in t for w in PROGRAM_WORDS) or "эхн" in t or "нэгд" in t:
                self.state = "name"
                return ["ask_name_again"]
            if self.pick_tries >= 1:
                self.result = "declined"
                return []
            self.pick_tries += 1
            return ["which_ask"]

        if self.state == "event_start":
            if not self.events:
                self.result = "declined"
                return ["event_none"]
            ev = self.events[0] if len(self.events) == 1 else match_event(text, self.events)
            if ev:
                return self._offer_event(ev)
            self.state = "event_pick"
            keys = ["event_list"]
            for i, e in enumerate(self.events):
                keys += [f"ord_{i + 1}", f"ev:{e['name']}", f"date:{e['at']}"]
            return keys + ["event_pick"]

        if self.state == "event_pick":
            ev = self._pick_event(text)
            if ev:
                return self._offer_event(ev)
            if self.pick_tries < 1:
                self.pick_tries += 1
                return ["event_pick"]
            self.result = "declined"          # шинэ асуулт гэж үзээд энгийн горимд
            return []

        if self.state == "book_offer":
            ans = self._yes_no(text)
            if ans and QUESTION.search(text.lower()):
                ans = None
            if ans is True:
                self.result = "book"           # phone_server цаг санал болгоно (account.py)
                return ["@book"]
            self.result = "saved"
            return ["declined"] if ans is False else []

        if self.state == "event_offer":
            ans = self._yes_no(text)
            if ans is None and any(w in text.lower() for w in JOIN_WORDS):
                ans = True                     # "бүртгүүлье"
            if ans and QUESTION.search(text.lower()):
                ans = None                     # "хаана болох вэ" ("болох" тийм биш) -> шинэ асуулт
            if ans is True:
                self.state = "name"
                return ["ask_name_again"]
            self.result = "declined"
            return ["declined"] if ans is False else []
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
            name = self._name(text)
            if not name:
                return ["ask_name_again"]
            self.name = name
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
            if ans is None and self.lang == "mn" and CONFIRM_YES.search(text.lower()):
                ans = True
            if ans is True:
                if self.book and not self.event:
                    self.save_pending, self.state = True, "book_offer"
                    return ["done_book"]
                self.result = "saved"
                return ["event_done" if self.event else "done"]
            # "зөв"-ийг STT "төв дүү", "гэсэн" гэж сонсдог -> ойлгоогүй бол дугаарыг хаяхгүй, дахин асууна
            # Ойлгомжгүй бол 2 удаа дахин асууна (2 дахь нь яаж хариулахыг тайлбарлана), 3 дахь нь л дугаарыг дахин асууна
            if ans is None and self.confirm_tries < 2:
                self.confirm_tries += 1
                if self.confirm_tries == 2:
                    return ["confirm_hint", "readback", f"digits:{self.phone}", "confirm"]
                return ["readback", f"digits:{self.phone}", "confirm"]
            self.phone, self.confirm_tries = None, 0
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
