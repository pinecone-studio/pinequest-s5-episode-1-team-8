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
STANDARD_ANSWER_MIGRATIONS = {
    "Хандсанд баярлалаа. Сайхан өдөр өнгөрүүлээрэй.":
        "Манайхаар үйлчлүүлсэнд баярлалаа. Өдрийг сайхан өнгөрүүлээрэй.",
    "За, манай ажилтан тан руу эргэж залгана. Таны нэрийг хэлж өгнө үү?":
        "За, манай ажилтан тан руу эргэж залгана. Та нэрээ хэлж өгнө үү?",
    "Бүртгэлд тань туслъя. Таны нэрийг хэлж өгнө үү?":
        "Бүртгэлд тань туслъя. Та нэрээ хэлж өгнө үү?",
}

# {name} -> байгууллагын нэр. Нэрийн араас нөхцөл залгахгүй байхаар бичсэн.
GREETING = ("Сайн байна уу. {name} байна. Үйлчилгээний чанарыг сайжруулах зорилгоор яриаг хадгална. "
            "Танд юугаар туслах вэ?")
FILLERS = ["Түр хүлээгээрэй, шалгаад хэлье.", "За, одоохон мэдээллийг нь харъя."]


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

def standard_faq(cfg: dict, topics: str) -> list[dict]:
    """Бүх салбарт хэрэгтэй FAQ: мэндчилгээ, баярлалаа, баяртай, юу асууж болох, ажилтан, бүртгэл,
    холбоо барих, хаяг, цагийн хуваарь. Утас/хаяг/цаг өгөөгүй бол тэр FAQ-г үүсгэхгүй."""
    topics = topics or "манай үйлчилгээ"
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
         "answer": (f"Би {cfg['name']} байгууллагын AI туслах байна. {topics[:1].upper() + topics[1:]} талаар "
                    "асууж болно. Бүртгүүлэх эсвэл ажилтантай холбогдох бол хэлээрэй.")},
        {"id": "human_request", "auto": True,
         "questions": ["Ажилтантай холбогдмоор байна", "Хүнтэй ярьмаар байна", "Оператортой холбоно уу",
                       "Менежертэй ярья", "Ажилтан руу шилжүүлээч", "Надруу эргэж залгаарай"],
         "answer": "За, манай ажилтан тан руу эргэж залгана. Та нэрээ хэлж өгнө үү?"},
        {"id": "register", "auto": True,
         "questions": ["Бүртгүүлмээр байна", "Бүртгүүлэх", "Бүртгүүлж болох уу", "Захиалга өгмөөр байна",
                       "Цаг захиалмаар байна", "Хүсэлт өгмөөр байна"],
         "answer": "Бүртгэлд тань туслъя. Та нэрээ хэлж өгнө үү?"},
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
                    "questions": ["Хэдэн цагаас хэдэн цаг хүртэл ажилладаг вэ", "Цагийн хуваарь",
                                  "Хэзээ ажилладаг вэ", "Амралтын өдөр ажилладаг уу"],
                    "answer": f"Манай цагийн хуваарь: {cfg['hours'].rstrip('.')}."})
    return faq


def load_faq(t: Tenant) -> dict:
    try:
        with open(t.faq_path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return {}
    # SIM-TRUNK-ийн стандарт хэллэг шинэчлэгдэхэд зөвхөн untouched auto FAQ-г шилжүүлнэ.
    # Гараар зассан хариулт (auto тэмдэггүй)-д хүрэхгүй.
    changed = False
    for row in data.get("faq", []):
        replacement = STANDARD_ANSWER_MIGRATIONS.get(row.get("answer")) if row.get("auto") else None
        if replacement:
            row["answer"] = replacement
            changed = True
    if changed:
        write_json(t.faq_path, data)
    return data


def refresh_faq(t: Tenant):
    """Загвар FAQ-г config-оос дахин үүсгэнэ ("auto": true). Хэрэглэгчийн гараар нэмсэн/засварласан
    ("auto" тэмдэггүй) FAQ, гараар өөрчилсөн мэндчилгээнд хүрэхгүй."""
    cfg = t.config()
    topics = join_or([x["label"] for x in cfg.get("clarify_topics", [])][:3]) if cfg.get("clarify_topics") else ""
    data = load_faq(t) or {"greeting": "", "fillers": FILLERS, "topics": {}, "faq": []}
    custom = [x for x in data.get("faq", []) if not x.get("auto")]
    custom_ids = {x["id"] for x in custom}
    data["faq"] = [x for x in standard_faq(cfg, topics) if x["id"] not in custom_ids] + custom
    if not data.get("greeting_custom"):
        data["greeting"] = GREETING.format(name=cfg.get("name", t.slug))
    write_json(t.faq_path, data)
