"""
Байгууллага (tenant) бүрийн өгөгдөл тусдаа хавтсанд: backend/data/tenants/<slug>/

  config.json   нэр, утас, и-мэйл, хаяг, цагийн хуваарь, дотуур дугаар (extension), эрх (plan)
  faq.json      түгээмэл асуулт (байгууллага үүсгэхэд загвараас автоматаар)
  knowledge/    мэдээлэл (RAG) — .md .txt .pdf .docx
  data/         дуудлагын лог (SQLite), Telegram тохиргоо

Вэб хүсэлт бүрт middleware нэвтэрсэн хэрэглэгчийн байгууллагыг request.state.tenant-д тавина.
"""
import json
import os
import re
import threading
import time

from config import TENANTS_DIR
from speech import number_words

DEFAULT_TENANT = "pinecone"
DEFAULT_NAME = "Pinecone Academy"
SLUG = re.compile(r"[a-z0-9][a-z0-9-]{1,31}")
PLANS = ("trial", "active", "suspended")
LOCK = threading.Lock()  # шинэ байгууллага үүсгэх (slug, дотуур дугаар давхцахгүй)

# Байгууллага бүрд загвараас үүснэ. {name}, {topics}, {phone_words} -> config-оос.
# Нэрийн араас нөхцөл залгахгүй байхаар бичсэн (монгол нөхцөл үгээс хамаарч өөрчлөгддөг).
DEFAULT_PHRASES = {
    "greeting": ("Сайн байна уу. {name} байна. Үйлчилгээний чанарыг сайжруулах зорилгоор яриаг хадгална. "
                 "Танд юугаар туслах вэ?"),
    "error": "Энэ мэдээллийг баталгаатай олж чадсангүй. Манай ажилтан тан руу эргэж холбогдох уу?",
    "repeat": "Уучлаарай, сайн ойлгосонгүй. Та дахин хэлж өгнө үү?",
    "clarify": "Та юуны талаар мэдэхийг хүсэж байна вэ? Жишээ нь {topics}.",
    "fillers": ["Түр хүлээгээрэй, шалгаад хэлье.", "За, одоохон мэдээллийг нь харъя."],
    "holds": ["Түр хүлээгээрэй.", "Одоохон хэлье.", "Мэдээллийг нь шалгаж байна.", "Бага зэрэг хүлээгээрэй.",
              "Одоохон олчихлоо.", "Түр хором хүлээгээрэй."],
    "lead": {
        "ask_phone": ("Баярлалаа. Тантай холбогдох утасны дугаараа хэлж өгнө үү. "
                      "Эсвэл утасныхаа товчлуураар бичиж болно."),
        "readback": "Таны дугаар",
        "confirm": "Зөв үү?",
        "phone_retry": ("Уучлаарай, дугаарыг сайн ойлгосонгүй. "
                        "Найман оронтой дугаараа утасныхаа товчлуураар бичнэ үү."),
        "done": ("Таны мэдээллийг амжилттай бүртгэлээ. Манай ажилтан тантай удахгүй холбогдоно. "
                 "Өөр асуух зүйл байна уу?"),
        "done_no_phone": ("Таны нэрийг бүртгэлээ. Дугаарыг тань авч чадсангүй тул манай {phone_words} "
                          "дугаар руу залгаарай. Өөр асуух зүйл байна уу?"),
        "declined": "За, ойлголоо. Өөр асуух зүйл байна уу?",
        "ask_name_again": "Та нэрээ хэлж өгнө үү?",
    },
    # Залгагч өөрийн бүртгэлийг кодоор шалгаж, өөрчлөх (account.py, people.py)
    "account": {
        "ask_code": ("Таны мэдээллийг шалгахын тулд дөрвөн оронтой бүртгэлийн кодоо "
                     "утасныхаа товчлуураар бичнэ үү."),
        "code_wrong": "Код таарсангүй. Дахин бичнэ үү.",
        "code_fail": ("Уучлаарай, кодыг баталгаажуулж чадсангүй. Кодоо мэдэхгүй бол манай ажилтантай "
                      "холбогдоно уу. Өөр асуух зүйл байна уу?"),
        "verified": "Баталгаажлаа.",
        "menu": ("Дугаараа солих бол нэг, цагаа солих бол хоёр, цагаа цуцлах бол гурав, бүртгэлээ цуцлах бол "
                 "дөрвийг дарна уу. Эсвэл хэлж болно."),
        "appt_is": "Таны уулзалтын цаг",
        "no_appt": "Танд одоогоор товлосон цаг алга.",
        "phone_is": "Таны бүртгэлтэй дугаар",
        "no_phone": "Таны бүртгэлд утасны дугаар алга.",
        "status_new": "Таны бүртгэл хүлээгдэж байна. Манай ажилтан удахгүй холбогдоно.",
        "status_contacted": "Манай ажилтан тантай холбогдсон байна.",
        "status_done": "Таны бүртгэл дууссан байна.",
        "status_canceled": "Таны бүртгэл цуцлагдсан байна.",
        "course_is": "Таны бүртгэл:",
        "no_course": "Таны бүртгэлд хөтөлбөр, эвентийн мэдээлэл алга.",
        "ask_cancel_reg": "Энэ бүртгэлээ цуцлах уу? Тийм бол нэг, үгүй бол хоёрыг дарна уу.",
        "reg_cancel_done": "Таны бүртгэлийг цуцаллаа. Манай ажилтанд мэдэгдлээ.",
        "attendance_yes": "Таныг эвентэд ирнэ гэж бүртгэсэн байна.",
        "attendance_no": "Таныг эвентэд ирэхгүй гэж бүртгэсэн тул бүртгэл цуцлагдсан байна.",
        "attendance_unknown": "Таны ирэх эсэхийг хараахан асуугаагүй байна. Эвентийн өмнөх өдөр манай AI залгаж асууна.",
        "ask_new_phone": "Шинэ дугаараа утасныхаа товчлуураар бичнэ үү.",
        "phone_retry": "Уучлаарай, найман оронтой дугаараа товчлуураар дахин бичнэ үү.",
        "new_phone_is": "Шинэ дугаар",
        "confirm": "Зөв бол нэг, буруу бол хоёрыг дарна уу.",
        "phone_done": "Таны дугаарыг солилоо.",
        "slots_intro": "Дараах сул цагууд байна.",
        "press_1": "Нэгийг дарвал",
        "press_2": "Хоёрыг дарвал",
        "press_3": "Гурвыг дарвал",
        "slot_pick_again": "Аль цагийг сонгох вэ? Нэг, хоёр, гурвын аль нэгийг дарна уу.",
        "you_chose": "Таны сонгосон цаг",
        "slot_taken": "Уучлаарай, тэр цаг саяхан захиалагдчихлаа.",
        "no_slots": "Уучлаарай, ойрын хугацаанд сул цаг алга. Манай ажилтан тантай холбогдоно.",
        "appt_done": "Таны цагийг солилоо. Шинэ цаг",
        "ask_cancel": "Энэ цагаа цуцлах уу? Тийм бол нэг, үгүй бол хоёрыг дарна уу.",
        "cancel_done": "Таны цагийг цуцаллаа. Манай ажилтанд мэдэгдлээ.",
        "unchanged": "За, өөрчлөхгүй үлдээлээ.",
        "anything_else": "Өөр асуух зүйл байна уу?",
        "your_code": "Таны бүртгэлийн код",
        "code_remember": "Энэ кодоороо залгаж мэдээллээ шалгах, цагаа солих боломжтой.",
        # Ажилтан (багш) утсаар бусдын бүртгэлийг өөрчлөх
        "staff_ask_pin": "Ажилтны зургаан оронтой кодоо утасныхаа товчлуураар бичнэ үү.",
        "staff_verified": ("Ажилтны эрхээр нэвтэрлээ. Хэний мэдээллийг өөрчлөх вэ? Нэрийг нь хэлэх эсвэл "
                           "бүртгэлийн кодыг нь бичнэ үү."),
        "target_is": "Олдсон бүртгэлийн код",
        "target_phone": "утасны дугаар",
        "confirm_target": "Энэ хүн мөн бол нэг, биш бол хоёрыг дарна уу.",
        "target_not_found": "Ийм бүртгэл олдсонгүй. Нэрийг нь дахин хэлэх эсвэл бүртгэлийн кодыг нь бичнэ үү.",
        "staff_next": "Өөр хүний мэдээлэл өөрчлөх бол нэрийг нь хэлнэ үү.",
    },
}
GREETING = DEFAULT_PHRASES["greeting"]
FILLERS = DEFAULT_PHRASES["fillers"]

class Tenant:
    def __init__(self, slug: str):
        if not SLUG.fullmatch(slug or ""):
            raise ValueError(f"Байгууллагын нэр (slug) буруу: {slug!r}")
        self.slug = slug
        self.dir = os.path.join(TENANTS_DIR, slug)

    def path(self, *parts) -> str:
        return os.path.join(self.dir, *parts)

    knowledge_dir = property(lambda self: self.path("knowledge"))
    faq_path = property(lambda self: self.path("faq.json"))
    config_path = property(lambda self: self.path("config.json"))
    training_path = property(lambda self: self.path("training", "examples.json"))
    auto_training_path = property(lambda self: self.path("training", "auto.json"))
    faq_index_dir = property(lambda self: self.path("faq_audio"))
    kb_index_dir = property(lambda self: self.path("knowledge_index"))
    recordings_dir = property(lambda self: self.path("recordings"))
    db_path = property(lambda self: self.path("data", "receptionist.db"))
    settings_path = property(lambda self: self.path("data", "settings.json"))

    def exists(self) -> bool:
        return os.path.exists(self.config_path)

    def config(self) -> dict:
        try:
            with open(self.config_path, encoding="utf-8") as f:
                return json.load(f)
        except (OSError, ValueError):
            return {"name": self.slug}

    def save_config(self, cfg: dict):
        write_json(self.config_path, cfg)

    def phrases(self, topics: list[str] | None = None) -> dict:
        """Загвар + config["phrases"] дахь гараар өөрчилсөн хэллэг -> бэлэн текст."""
        cfg = self.config()
        over = cfg.get("phrases", {})
        topics = topics or [t["label"] for t in cfg.get("clarify_topics", [])][:3]
        values = {"name": cfg.get("name", self.slug), "topics": join_or(topics) if topics else "",
                  "phone_words": number_words(cfg["phone"], phone=True) if cfg.get("phone") else ""}

        def fill(text):
            return text.format(**values) if isinstance(text, str) else [fill(t) for t in text]

        defaults = dict(DEFAULT_PHRASES)
        if not topics:                   # мэдээлэлд "## гарчиг" алга -> жишээгүй тодруулах асуулт
            defaults["clarify"] = "Та юуны талаар мэдэхийг хүсэж байна вэ? Асуултаа арай тодорхой хэлж өгнө үү."
        out = {k: fill(over.get(k, v)) for k, v in defaults.items() if k not in ("lead", "account")}
        lead = {**DEFAULT_PHRASES["lead"], **over.get("lead", {})}
        if not cfg.get("phone"):
            lead["done_no_phone"] = ("Таны нэрийг бүртгэлээ. Дугаарыг тань авч чадсангүй тул дахин "
                                     "залгаж холбогдоорой. Өөр асуух зүйл байна уу?")
        out["lead"] = {k: fill(v) for k, v in lead.items()}
        out["account"] = {k: fill(v) for k, v in {**DEFAULT_PHRASES["account"], **over.get("account", {})}.items()}
        return out


def write_json(path: str, data):
    """Түр файлд бичээд солино (дундаас нь тасарвал хуучин файл эвдрэхгүй)."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def join_or(items: list[str]) -> str:
    items = [i for i in items if i]
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " эсвэл " + items[-1]


def all_tenants() -> list[Tenant]:
    if not os.path.isdir(TENANTS_DIR):
        return []
    return [Tenant(d) for d in sorted(os.listdir(TENANTS_DIR)) if SLUG.fullmatch(d) and Tenant(d).exists()]


# ---------------- шинэ байгууллага ----------------

LATIN = dict(zip("абвгдеёжзийклмноөпрстуүфхцчшщъыьэюя",
                 ["a", "b", "v", "g", "d", "e", "yo", "j", "z", "i", "i", "k", "l", "m", "n", "o", "u", "p",
                  "r", "s", "t", "u", "u", "f", "kh", "ts", "ch", "sh", "sh", "", "y", "", "e", "yu", "ya"]))


def make_slug(name: str) -> str:
    """"Шүдний эмнэлэг Гэрэл" -> "shudnii-emneleg-gerel" (давхцвал -2, -3...)."""
    base = "".join(LATIN.get(ch, ch) for ch in name.lower())
    base = re.sub(r"[^a-z0-9]+", "-", base).strip("-")[:28] or "org"
    if len(base) < 2:
        base = f"org-{base}"
    slug, n = base, 2
    while os.path.exists(os.path.join(TENANTS_DIR, slug)):
        slug, n = f"{base}-{n}", n + 1
    return slug


def next_extension() -> str:
    """Дотуур дугаар: 1000, 1001, ... (залгахад аль байгууллага болохыг олно)"""
    used = {str(t.config().get("extension")) for t in all_tenants()}
    n = 1000
    while str(n) in used:
        n += 1
    return str(n)


def clean_phone(phone: str) -> str:
    return re.sub(r"[^\d+]", "", phone)


def create(name: str, phone: str = "", email: str = "", address: str = "", hours: str = "",
           slug: str | None = None) -> Tenant:
    """Шинэ байгууллага: config, загвар FAQ, хоосон мэдээллийн хавтас."""
    name = " ".join(name.split())
    if not 2 <= len(name) <= 80:
        raise ValueError("Байгууллагын нэр 2-80 тэмдэгт")
    t = Tenant(slug or make_slug(name))
    cfg = {"name": name, "extension": next_extension(), "phone": clean_phone(phone),
           "email": email.strip(), "address": address.strip(), "hours": hours.strip(),
           "plan": "trial", "created_at": time.time()}
    t.save_config({k: v for k, v in cfg.items() if v != ""})
    refresh_faq(t)
    os.makedirs(t.knowledge_dir, exist_ok=True)
    return t


def ensure_default() -> Tenant:
    """Анх асахад жишиг байгууллага (admin-ий байгууллага) байхгүй бол үүсгэнэ."""
    t = Tenant(DEFAULT_TENANT)
    return t if t.exists() else create(DEFAULT_NAME, slug=DEFAULT_TENANT)


# ---------------- загвар FAQ ----------------

def standard_faq(cfg: dict, phrases: dict) -> list[dict]:
    """Бүх салбарт хэрэгтэй FAQ: мэндчилгээ, баярлалаа, баяртай, юу асууж болох, ажилтан, бүртгэл,
    холбоо барих, хаяг, цагийн хуваарь. Утас/хаяг/цаг өгөөгүй бол тэр FAQ-г үүсгэхгүй."""
    topics = phrases.get("topics_text") or "манай үйлчилгээ"
    faq = [
        {"id": "smalltalk_hello", "auto": True,
         "questions": ["Сайн байна уу", "Сайн уу", "Байна уу", "Алло", "Сайн байцгаана уу", "Мэнд хүргэе"],
         "answer": f"Сайн байна уу. Та юуны талаар мэдэхийг хүсэж байна вэ? Жишээ нь {topics}."},
        {"id": "smalltalk_thanks", "auto": True,
         "questions": ["Баярлалаа", "Маш их баярлалаа", "За ойлголоо баярлалаа", "Ойлголоо"],
         "answer": "Зүгээр зүгээр. Өөр асуух зүйл байна уу?"},
        {"id": "smalltalk_bye", "auto": True,
         "questions": ["Баяртай", "За баяртай", "Өөр асуух зүйл алга", "Байхгүй ээ", "Үгүй баярлалаа", "Болоо"],
         "answer": "Манайхаар үйлчлүүлсэнд баярлалаа. Өдрийг сайхан өнгөрүүлээрэй."},
        {"id": "smalltalk_capabilities", "auto": True,
         "questions": ["Юу асууж болох вэ", "Та юу мэдэх вэ", "Та хэн бэ", "Чи робот уу", "Ямар мэдээлэл өгөх вэ"],
         "answer": (f"Би {cfg['name']} байгууллагын AI туслах байна. {topics[:1].upper() + topics[1:]} талаар асууж болно. "
                    "Бүртгүүлэх эсвэл ажилтантай холбогдох бол хэлээрэй.")},
        {"id": "human_request", "auto": True,
         "questions": ["Ажилтантай холбогдмоор байна", "Хүнтэй ярьмаар байна", "Оператортой холбоно уу",
                       "Менежертэй ярья", "Ажилтан руу шилжүүлээч", "Надруу эргэж залгаарай"],
         "answer": "За, манай ажилтан тан руу эргэж залгана. Та нэрээ хэлж өгнө үү?"},
        {"id": "register", "auto": True,
         "questions": ["Бүртгүүлмээр байна", "Бүртгүүлэх", "Бүртгүүлж болох уу", "Захиалга өгмөөр байна",
                       "Цаг захиалмаар байна", "Хүсэлт өгмөөр байна"],
         "answer": "Бүртгэлд тань туслъя. Та нэрээ хэлж өгнө үү?"},
        # Хариулт нь өөрөө код асууна -> phone_server бүртгэлээ шалгах/өөрчлөх урсгал эхлүүлнэ (account.py)
        {"id": "my_account", "auto": True,
         "questions": ["Цагаа солимоор байна", "Уулзалтын цагаа өөрчлөх", "Дугаараа солимоор байна",
                       "Бүртгэлээ шалгах", "Миний цаг хэзээ билээ", "Цагаа цуцлах", "Бүртгэлийн код",
                       "Бүртгэлээ өөрчлөх", "Уулзалтаа хойшлуулмаар байна", "Утасны дугаараа солих",
                       "Дугаараа солих гэсэн юм", "Бүртгэлээ цуцлах", "Эвентэд очиж чадахгүй боллоо",
                       "Хөтөлбөрт суухаа больсон"],
         "answer": phrases["account"]["ask_code"]},
        # Ажилтан (багш) бусдын бүртгэлийг утсаар өөрчилнө — 6 оронтой ажилтны код асууна
        {"id": "staff_mode", "auto": True,
         "questions": ["Ажилтны горим", "Би ажилтан байна", "Багш байна мэдээлэл өөрчлөх гэсэн юм",
                       "Сурагчийн мэдээлэл өөрчлөх", "Ажилтнаар нэвтрэх", "Сурагчийн цагийг солих",
                       "Багшийн горим"],
         "answer": phrases["account"]["staff_ask_pin"]},
    ]
    name = cfg["name"]
    # Утсан ярианы ердийн нөхцөл (байгууллагаас үл хамаарна). repeat_last -> phone_server өмнөх хариултаа дахин тоглуулна.
    # Нэрийн араас нөхцөл залгахгүй (монгол нөхцөл нэрээс хамаарч өөрчлөгддөг).
    faq += [
        {"id": "phone_hear_check", "auto": True,
         "questions": ["Сонсогдож байна уу", "Намайг сонсож байна уу", "Алло сонсогдож байна уу", "Сонсож байна уу",
                       "Миний дуу сонсогдож байна уу", "Алло алло", "Байна уу сонсогдож байна уу"],
         "answer": "Тийм, сайн сонсогдож байна. Танд юугаар туслах вэ?"},
        {"id": "phone_bad_line", "auto": True,
         "questions": ["Сонсогдохгүй байна", "Сайн сонсогдохгүй байна", "Тасраад байна", "Чимээ ихтэй байна",
                       "Дуу чинь тасраад байна", "Юу ч сонсогдохгүй байна", "Холболт муу байна"],
         "answer": "Уучлаарай, холболт муу байж магадгүй. Асуултаа арай чанга, тодорхой хэлж өгнө үү?"},
        {"id": "repeat_last", "auto": True,
         "questions": ["Дахиад хэлээч", "Дахин хэлж өгөөч", "Юу гэнээ", "Давтаад хэлээч", "Сайн ойлгосонгүй дахиад хэлээч",
                       "Удаан хэлээч", "Арай удаан ярина уу", "Сая юу гэсэн бэ", "Дахиад нэг хэлээд өгөөч"],
         "answer": "За, дахин хэлье."},
        {"id": "phone_wait", "auto": True,
         "questions": ["Түр хүлээгээрэй", "Түр байзаарай", "Нэг минут хүлээгээрэй", "Түр хүлээж байгаарай", "Байз байз",
                       "Хүлээж байгаарай би бичих юм авъя"],
         "answer": "За, хүлээж байя. Бэлэн болохоороо хэлээрэй."},
        {"id": "phone_which_org", "auto": True,
         "questions": ["Энэ ямар байгууллага вэ", "Хаашаа залгачихав", "Хаана залгасан бэ", f"{name} мөн үү",
                       "Энэ хаана вэ", "Хаана руу залгачихсан бэ"],
         "answer": f"Тийм, {name} байна. Танд юугаар туслах вэ?"},
        {"id": "phone_call_later", "auto": True,
         "questions": ["Дараа залгая", "Одоо завгүй байна дараа залгая", "Би дараа ярья", "Дараа дахиад залгана",
                       "Одоо болохгүй нь дараа ярья"],
         "answer": "За, болно. Хүссэн үедээ дахин залгаарай. Баярлалаа."},
        {"id": "phone_wrong_number", "auto": True,
         "questions": ["Буруу залгачихлаа", "Андуураад залгачихлаа", "Уучлаарай буруу дугаар", "Өөр газар руу залгах гэсэн юм"],
         "answer": "Зүгээр ээ. Сайхан өдөр өнгөрүүлээрэй."},
    ]
    if cfg.get("phone"):
        faq.append({"id": "contact_phone", "auto": True,
                    "questions": ["Утасны дугаар хэд вэ", "Танай утас хэд вэ", "Холбоо барих дугаар",
                                  "Ямар дугаар руу залгах вэ"],
                    "answer": f"Манай утасны дугаар {number_words(cfg['phone'], phone=True)}."})
    if cfg.get("address"):
        faq.append({"id": "location", "auto": True,
                    "questions": ["Хаана байрладаг вэ", "Хаягаа хэлээч", "Танай оффис хаана байдаг вэ",
                                  "Яаж очих вэ"],
                    "answer": f"Манай хаяг: {cfg['address'].rstrip('.')}."})
    if cfg.get("hours"):
        faq.append({"id": "hours", "auto": True,
                    "questions": ["Хэдэн цагаас хэдэн цаг хүртэл ажилладаг вэ", "Цагийн хуваарь", "Хэзээ ажилладаг вэ",
                                  "Амралтын өдөр ажилладаг уу"],
                    "answer": f"Манай цагийн хуваарь: {cfg['hours'].rstrip('.')}."})
    return faq

def load_faq(t: Tenant) -> dict:
    """faq.json (уншина л, SIM-TRUNK шиг өөрчлөхгүй)."""
    try:
        with open(t.faq_path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def refresh_faq(t: Tenant):
    """Загвар FAQ-г config-оос дахин үүсгэнэ ("auto": true). Хэрэглэгчийн гараар нэмсэн/засварласан
    ("auto" тэмдэггүй) FAQ-д хүрэхгүй."""
    cfg = t.config()
    phrases = t.phrases()
    topics = [x["label"] for x in cfg.get("clarify_topics", [])][:3]
    phrases["topics_text"] = join_or(topics) if topics else ""
    data = {"greeting": phrases["greeting"], "fillers": phrases["fillers"], "topics": {}, "faq": []}
    if os.path.exists(t.faq_path):
        with open(t.faq_path, encoding="utf-8") as f:
            data = json.load(f)
    custom = [x for x in data.get("faq", []) if not x.get("auto")]
    custom_ids = {x["id"] for x in custom}
    data["faq"] = [x for x in standard_faq(cfg, phrases) if x["id"] not in custom_ids] + custom
    if not data.get("greeting_custom"):
        data["greeting"] = phrases["greeting"]
    write_json(t.faq_path, data)
