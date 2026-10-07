"""SIM-TRUNK english.py-ийн вэбийн хэсэг (1-213-р мөр) — ЯГ хуулбар. Дуудлагын үеийн хэсэг (англи бүртгэл,
хайлт) SIM-TRUNK-ийн phone_server-т ажиллана.

Хоёр хэлтэй горим: config.json "languages": ["mn", "en"] үед англиар ярьсан залгагчид англиар хариулна.

  Хэл таних  stt.BilingualSTT: олон хэлтэй Whisper хэлийг тодорхойлоод англи бол өөрөө, монгол бол
             монгол fine-tune таниулна
  Хариулт    tenants/<slug>/english.json: монгол хариулт бүрийн англи орчуулга (байгууллага вэбээр
             бичнэ, AI зохиохгүй). Орчуулаагүй мэдээллийг англиар хэлэхгүй -> ажилтан эргэж залгана
  Хайлт      bge-m3 олон хэлтэй: англи асуулт <-> англи орчуулга, англи асуулт, монгол FAQ асуулт,
             монгол мэдээлэл (орчуулаагүйг ч таньж "монголоор л байна" гэж хэлэхэд)
  Аудио      F5 base (англи) + F5-ийн англи лавлах хоолой, scripts/build_en.py урьдчилан бэлдэнэ

english.json:
  {"phrases": {"greeting_suffix": "...", ...},              # DEFAULT_PHRASES_EN-ийг дарна
   "answers": {"<монгол бичвэрийн hash>": {"mn": "...", "en": "..."}},
   "questions": {"<faq id>": ["How much does it cost?", ...]}}
Монгол бичвэр өөрчлөгдвөл hash өөрчлөгдөж хуучин орчуулга тоглогдохгүй ("хуучирсан" гэж харагдана).
"""
import json
import os
import re


import tenant as tenants
from audio_files import text_hash

EN_DIGITS = ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine"]
DEFAULT_PHRASES_EN = {
    "greeting_suffix": "For English, please go ahead and speak English.",
    "repeat": "Sorry, I didn't catch that. Could you say it again?",
    "error": "Sorry, I couldn't find that information. Would you like a staff member to call you back?",
    "mongolian_only": ("Sorry, I have that information only in Mongolian. "
                       "Would you like a staff member to call you back?"),
    "holds": ["One moment, please.", "Let me check that for you."],
    "lead": {
        "ask_phone": "Thank you. What phone number can we reach you at? You can also type it on your keypad.",
        "readback": "Your number is",
        "confirm": "Is that correct?",
        "phone_retry": "Sorry, I didn't get that. Please type your eight digit phone number on your keypad.",
        "done": ("Thank you, you're all set. A staff member will contact you soon. "
                 "Is there anything else I can help you with?"),
        "done_no_phone": ("I've noted your name, but I couldn't get your number. Please call us at {phone_en}. "
                          "Is there anything else I can help you with?"),
        "declined": "Alright. Is there anything else I can help you with?",
        "ask_name_again": "Sure. May I have your name, please?",
    },
}
# Бүх байгууллагад автоматаар үүсдэг FAQ (tenant.standard_faq)-ийн англи хувилбар. Хаяг, цагийн хуваарь
# монгол бичвэр тул байгууллага өөрөө орчуулна.
STANDARD_EN = {
    "smalltalk_hello": {"answer": "Hello, this is {name}. How can I help you?",
                        "questions": ["Hello", "Hi", "Good morning", "Hello, is anyone there?"]},
    "smalltalk_thanks": {"answer": "You're welcome. Is there anything else I can help you with?",
                         "questions": ["Thank you", "Thanks a lot", "Okay, thanks", "I see, thank you"]},
    "smalltalk_bye": {"answer": "Thank you for calling {name}. Have a nice day!",
                      "questions": ["Goodbye", "Bye", "That's all", "Nothing else, thanks", "No, that's it"]},
    "smalltalk_capabilities": {"answer": ("I'm the AI assistant of {name}. You can ask me about our services, "
                                          "or ask to register or to talk to a staff member."),
                               "questions": ["What can I ask you?", "Who are you?", "Are you a robot?",
                                             "What do you know?"]},
    "human_request": {"answer": "Sure, a staff member will call you back. May I have your name, please?",
                      "questions": ["I want to talk to a person", "Can I speak to someone?",
                                    "Connect me to an operator", "Please call me back", "I need a human"]},
    "register": {"answer": "I can help you register. May I have your name, please?",
                 "questions": ["I want to register", "I'd like to sign up", "How do I enroll?",
                               "I want to book an appointment", "Can I make a reservation?"]},
    "contact_phone": {"answer": "Our phone number is {phone_en}.",
                      "questions": ["What is your phone number?", "What number should I call?",
                                    "How can I contact you?"]},
}

YES_EN = {"yes", "yeah", "yep", "sure", "correct", "right", "ok", "okay", "please", "absolutely", "that's"}
NO_EN = {"no", "nope", "not", "wrong", "incorrect", "don't", "dont"}
NUM_EN = {**{w: str(i) for i, w in enumerate(EN_DIGITS)}, "oh": "0", "o": "0", "for": "4", "to": "2", "too": "2",
          "ate": "8", "won": "1"}
AMBIGUOUS = {"oh", "o", "for", "to", "too", "ate", "won"}   # дугаар эхэлсний дараа л цифр гэж үзнэ


def phone_en(phone: str) -> str:
    """72700800 -> "seven two seven zero, zero eight zero zero" (4-4 бүлэг)."""
    d = re.sub(r"\D", "", phone or "")
    words = [EN_DIGITS[int(c)] for c in d]
    return ", ".join(" ".join(words[i:i + 4]) for i in range(0, len(words), 4))


ONES = ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten", "eleven", "twelve",
        "thirteen", "fourteen", "fifteen", "sixteen", "seventeen", "eighteen", "nineteen"]
TENS = ["", "", "twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety"]


def say_int(n: int) -> str:
    if n < 20:
        return ONES[n]
    if n < 100:
        return TENS[n // 10] + ("-" + ONES[n % 10] if n % 10 else "")
    if n < 1000:
        return ONES[n // 100] + " hundred" + (" " + say_int(n % 100) if n % 100 else "")
    for size, word in ((10 ** 9, "billion"), (10 ** 6, "million"), (1000, "thousand")):
        if n >= size:
            return say_int(n // size) + f" {word}" + (" " + say_int(n % size) if n % size else "")
    return str(n)


def speak_en(text: str) -> str:
    """F5 англи загвар цифрийг тогтворгүй уншдаг -> үгээр. 8 оронтой (утас) -> цифр бүрээр."""
    text = re.sub(r"(\d{1,2}:\d{2})\s*[-–]\s*(\d{1,2}:\d{2})", r"\1 to \2", text)        # 9:00-18:00
    text = re.sub(r"\s*(₮|\bMNT\b|\bтөг\.?)", " tugriks", text)
    text = re.sub(r"\b\d{8}\b", lambda m: phone_en(m.group(0)), text)
    text = re.sub(r"(\d+)\s*%", lambda m: say_int(int(m.group(1))) + " percent", text)
    text = re.sub(r"\b(\d{1,2}):(\d{2})\b",
                  lambda m: say_int(int(m.group(1))) + ("" if m.group(2) == "00" else " " + say_int(int(m.group(2)))),
                  text)
    text = re.sub(r"\d{1,3}(?:,\d{3})+|\d+", lambda m: say_int(int(m.group(0).replace(",", ""))), text)
    return re.sub(r"\s+", " ", text.replace("&", " and ")).strip()


def english_path(t: "tenants.Tenant") -> str:
    return t.path("english.json")


def load(t: "tenants.Tenant | None" = None) -> dict:
    t = t or tenants.current()
    try:
        with open(english_path(t), encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        data = {}
    return {"phrases": data.get("phrases", {}), "answers": data.get("answers", {}),
            "questions": data.get("questions", {})}


def save(t: "tenants.Tenant", data: dict):
    tmp = english_path(t) + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    os.replace(tmp, english_path(t))


def enabled(t: "tenants.Tenant | None" = None) -> bool:
    return "en" in (t or tenants.current()).config().get("languages", ["mn"])


def values(t: "tenants.Tenant") -> dict:
    cfg = t.config()
    return {"name": cfg.get("name", t.slug), "phone_en": phone_en(cfg.get("phone", ""))}


def phrases(t: "tenants.Tenant | None" = None, custom: bool = True) -> dict:
    """Загвар + english.json-ийн phrases -> бэлэн англи хэллэг ({name}, {phone_en} бөглөсөн).
    custom=False: зөвхөн загвар (вэбээс ирсэн утга өөрчлөгдсөн эсэхийг харьцуулахад)."""
    t = t or tenants.current()
    over, vals = (load(t)["phrases"] if custom else {}), values(t)

    def fill(x):
        return x.format(**vals) if isinstance(x, str) else [fill(y) for y in x]

    out = {k: fill(over.get(k, v)) for k, v in DEFAULT_PHRASES_EN.items() if k != "lead"}
    lead = {**DEFAULT_PHRASES_EN["lead"], **over.get("lead", {})}
    if not t.config().get("phone"):
        lead["done_no_phone"] = ("I've noted your name, but I couldn't get your number. Please call us again. "
                                 "Is there anything else I can help you with?")
    out["lead"] = {k: fill(v) for k, v in lead.items()}
    return out


def items(t: "tenants.Tenant | None" = None) -> list[dict]:
    """Орчуулах бүх хариулт: FAQ хариулт + мэдээллийн өгүүлбэр (бэлдсэн индексээс).
    -> [{hash, kind, id, mn, en, questions_en, standard}]"""
    t = t or tenants.current()
    data, vals = load(t), values(t)
    out, seen = [], set()
    try:
        with open(t.faq_path, encoding="utf-8") as f:
            faq = json.load(f)["faq"]
    except (OSError, ValueError, KeyError):
        faq = []
    for x in faq:
        if "TODO" in x["answer"]:
            continue
        h = text_hash(x["answer"])
        std = STANDARD_EN.get(x["id"]) if x.get("auto") else None
        tr = data["answers"].get(h, {}).get("en") or (std["answer"].format(**vals) if std else None)
        if x["id"] == "contact_phone" and std and not t.config().get("phone"):
            tr = None
        out.append({"hash": h, "kind": "faq", "id": x["id"], "mn": x["answer"], "en": tr,
                    "questions_en": data["questions"].get(x["id"]) or (std["questions"] if std else []),
                    "mn_questions": x["questions"], "standard": bool(std)})
        seen.add(h)
    try:
        with open(os.path.join(t.kb_index_dir, "facts.json"), encoding="utf-8") as f:
            facts = json.load(f)["facts"]
    except (OSError, ValueError, KeyError):
        facts = []
    for x in facts:
        h = text_hash(x["text"])
        if h in seen:
            continue
        seen.add(h)
        out.append({"hash": h, "kind": "fact", "id": None, "mn": x["text"], "section": x.get("section"),
                    "en": data["answers"].get(h, {}).get("en"), "questions_en": [], "mn_questions": [],
                    "standard": False})
    return out


def stale(t: "tenants.Tenant | None" = None) -> list[dict]:
    """Монгол бичвэр нь өөрчлөгдсөн (одоо байхгүй) орчуулгууд."""
    t = t or tenants.current()
    current = {x["hash"] for x in items(t)}
    return [{"hash": h, **v} for h, v in load(t)["answers"].items() if h not in current]
