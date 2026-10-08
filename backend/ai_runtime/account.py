"""
Залгагч өөрийн бүртгэлийг утсаар шалгаж, өөрчлөх (хувийн RAG, people.py).

  "Цагаа солимоор байна" (FAQ my_account) -> "Бүртгэлийн кодоо товчлуураар бичнэ үү"
  -> код таарвал зөвхөн ТЭР хүний баримтуудаас хайна (бусдын мэдээлэл хэзээ ч хайлтад орохгүй)
  -> дугаар солих / цаг солих (сул цагуудаас) / цуцлах / цаг, дугаар, төлөв асуух
  -> "Зөв бол нэг" гэж баталсны дараа л өгөгдлийн санд бичнэ -> ажилтанд мэдэгдэл

Ажилтан (багш) — бусдын бүртгэлийг өөрчлөх (FAQ staff_mode):
  "Ажилтны горим" -> 6 оронтой ажилтны код -> "Болдын цагийг Баасан гараг руу шилжүүл"
  -> БҮХ хүний баримтаас нэрээр хайна -> "Олдсон бүртгэлийн код 4720, утас 9911 2233. Энэ хүн мөн бол нэг"
  -> тэр хүний цаг/дугаарыг сольж, дараагийн хүн рүү шилжинэ (өгөгдлийн сан руу гараар орохгүй)

Бүх хариулт бэлэн аудио: хэллэг (tenant.DEFAULT_PHRASES["account"]), цифр, огноо (people.all_date_texts).
Дуудлагын үеэр LLM, TTS ажиллахгүй. Хайлт: bge-m3 (утасны AI-д ачаалагдсан) + үгийн язгуурын давхцал.

handle(text) / handle_dtmf(digits) -> тоглуулах түлхүүрүүд:
  "<хэллэг>"          tenant.DEFAULT_PHRASES["account"][key]
  "digits:99112233"   дугаарыг цифр бүрээр
  "date:2026-10-17T10:00"  гараг, сар, өдөр, цаг
  None -> энэ нь урсгалын хариулт биш (шинэ асуулт) -> энгийн горимд буцна
"""
import re
from datetime import datetime

import numpy as np

import people
from lead import parse_phone, yes_no

MAX_CODE_TRIES = 3
MATCH = 0.85            # bge-m3 (+үгийн давхцал): хүсэлтүүд >= 0.90, ерөнхий асуулт <= 0.80 (test_account.py --real)
LEX_WEIGHT = 0.15
OFFER = 3               # нэг удаад санал болгох сул цаг

# Залгагчийн хүсэлтүүд (хувийн баримтуудтай хамт хайлтад орно)
INTENTS = {
    "cancel_registration": ["Бүртгэлээ цуцлах", "Бүртгэлээ цуцалмаар байна", "Эвентэд очиж чадахгүй боллоо",
                            "Хөтөлбөрт суухаа больсон", "Оролцож чадахгүй нь", "Ирж чадахгүй нь цуцалъя", "Явахгүй болсон"],
    "change_phone": ["Дугаараа солимоор байна", "Утасны дугаараа өөрчлөх", "Шинэ дугаар өгье", "Дугаар солих",
                     "Дугаар маань солигдсон"],
    "change_time": ["Цагаа солимоор байна", "Өөр цаг авъя", "Уулзалтын цагаа хойшлуулах", "Цагаа өөрчлөх",
                    "Өөр өдөр болох уу", "Цагаа шилжүүлэх"],
    "cancel": ["Цагаа цуцлах", "Уулзалтаа цуцалмаар байна", "Товлосон цагаа цуцлах"],
    "ask_time": ["Миний цаг хэзээ билээ", "Хэдэн цагт очих вэ", "Уулзалт хэзээ вэ", "Хэдний өдөр очих вэ"],
    "ask_phone": ["Ямар дугаар бүртгэлтэй вэ", "Миний дугаар зөв үү", "Бүртгэлтэй дугаараа шалгах"],
    "ask_status": ["Бүртгэл маань ямар байгаа вэ", "Бүртгэл баталгаажсан уу", "Хүсэлт маань хаана явж байна"],
    "ask_attendance": ["Эвентэд ирэх эсэх маань бүртгэгдсэн үү", "Ирнэ гэж бүртгэгдсэн үү", "Намайг ирнэ гэж тэмдэглэсэн үү",
                       "Ирэх эсэхээ шалгах"],
}
# Ажилтны команд ("Болдын цагийг нь шилжүүл" — нэрийг хассаны дараа)
STAFF_INTENTS = {
    "cancel_registration": ["бүртгэлийг нь цуцал", "хөтөлбөрөөс хас", "эвентээс хас", "ирэхгүй гэсэн"],
    "change_phone": ["дугаарыг нь солих", "утасны дугаарыг нь өөрчил", "шинэ дугаар оруул", "дугаар солих"],
    "change_time": ["цагийг нь шилжүүл", "цагийг нь солих", "өөр өдөр рүү шилжүүл", "цагийг өөрчил",
                    "уулзалтыг нь хойшлуул", "руу шилжүүл"],
    "cancel": ["цагийг нь цуцал", "уулзалтыг нь цуцлах"],
    "ask_time": ["цаг нь хэзээ вэ", "хэдэн цагт ирэх вэ", "уулзалт нь хэзээ"],
    "ask_phone": ["дугаар нь хэд вэ", "ямар дугаартай вэ"],
    "ask_status": ["бүртгэл нь ямар байгаа вэ", "төлөв нь юу вэ"],
    "ask_attendance": ["ирэх үү", "ирнэ гэсэн үү", "ирэх эсэх нь"],
}
DOC_INTENT = {"phone": "ask_phone", "appointment": "ask_time", "status": "ask_status", "attendance": "ask_attendance"}
MENU_KEYS = {"1": "change_phone", "2": "change_time", "3": "cancel", "4": "cancel_registration"}
ORDINALS = {"нэг": 0, "эхн": 0, "нэгд": 0, "хоёр": 1, "хоёрд": 1, "гура": 2, "гурв": 2, "сүүл": 2}
WEEKDAY_STEMS = {"дава": 0, "мягм": 1, "лхаг": 2, "пүрэ": 3, "пүрв": 3, "баас": 4, "бямб": 5, "ням": 6}


def stems(text: str) -> set[str]:
    return {w[:4] for w in re.findall(r"[а-яөүёa-z0-9]+", text.lower()) if len(w) >= 2}


class Search:
    """Хувийн RAG-ийн хайлт. embed(list[str]) -> normalized векторууд (bge-m3 query)."""

    def __init__(self, embed):
        self.embed = embed
        self.cache: dict[str, np.ndarray] = {}

    def vectors(self, texts: list[str]) -> np.ndarray:
        todo = [t for t in dict.fromkeys(texts) if t not in self.cache]
        if todo:
            for t, v in zip(todo, self.embed(todo)):
                self.cache[t] = np.asarray(v, np.float32)
        return np.stack([self.cache[t] for t in texts])

    def rank(self, query: str, docs: list[tuple[object, str]]) -> list[tuple[object, float]]:
        """docs = [(түлхүүр, текст)] -> [(түлхүүр, оноо)] өндрөөс нь. Нэг түлхүүрт олон текст байж болно."""
        if not docs:
            return []
        q = self.vectors([query])[0]
        sims = self.vectors([t for _, t in docs]) @ q
        qs = stems(query)
        best: dict = {}
        for (key, text), s in zip(docs, sims):
            lex = len(qs & stems(text)) / len(qs) if qs else 0.0
            best[key] = max(best.get(key, -1.0), float(s) + LEX_WEIGHT * lex)
        return sorted(best.items(), key=lambda x: -x[1])


def detect_intent(search: Search, text: str) -> str | None:
    """Код асуухаас өмнө: залгагч юу хүссэн бэ (хувийн өгөгдөлгүй, зөвхөн хүсэлтүүдээс)."""
    ranked = search.rank(text, [(k, q) for k, qs in INTENTS.items() for q in qs])
    return ranked[0][0] if ranked and ranked[0][1] >= MATCH else None


CHANGE_STEMS = ("шилж", "соли", "солъ", "соль", "өөрч", "хойш", "урагш")
CANT_GO = ("чадах", "больс", "явах", "суух", "оролц", "ирэхг", "очихг")


def keyword_intent(text: str) -> str | None:
    """Богино команд үгээр (вэбийн assistant.py-тэй ижил): "цуцал" -> бүртгэл/цаг, "шилжүүл", "дугаарыг соль"."""
    st = stems(text)
    low = text.lower()
    reg = any(x.startswith(("бүрт", "хөтө", "эвен", "сурга", "boot")) for x in st)
    if any(x.startswith("цуца") for x in st):
        return "cancel_registration" if reg or not any(x.startswith(("цаг", "уулз")) for x in st) else "cancel"
    if any(c in low for c in CANT_GO) and any(x.startswith(("чада", "боло", "боль")) for x in st):
        return "cancel_registration"
    if any(x.startswith(c) for x in st for c in CHANGE_STEMS):
        if any(x.startswith("дуга") or x.startswith("утас") or x.startswith("утсы") for x in st):
            return "change_phone"
        return "change_time"
    return None


def detect_staff_intent(search: Search, text: str) -> str | None:
    """Хувийн RAG-ийн хайлт (bge-m3) + товч командын үгс."""
    ranked = search.rank(text, [(k, q) for src in (STAFF_INTENTS, INTENTS) for k, qs in src.items() for q in qs])
    if ranked and ranked[0][1] >= MATCH:
        return ranked[0][0]
    return keyword_intent(text)


class AccountFlow:
    def __init__(self, tdir: str, search: Search, intent: str | None = None, call_uuid: str | None = None,
                 now: datetime | None = None, staff: bool = False):
        self.tdir, self.search, self.intent, self.call_uuid = tdir, search, intent, call_uuid
        self._now = now
        self.staff = staff            # True: ажилтан бусдын бүртгэлийг өөрчилнө
        # code | staff_code | target | target_confirm | menu | new_phone | phone_confirm | slot | slot_confirm | cancel_confirm
        self.state = "staff_code" if staff else "code"
        self.candidates: list[dict] = []   # ажилтны хайлтаар олдсон хүмүүс
        self.command = ""             # "цагийг нь Баасан руу" (нэргүй) -> хүнийг баталсны дараа гүйцэтгэнэ
        self.lead: dict | None = None
        self.tries = 0
        self.new_phone = None
        self.offered: list[datetime] = []
        self.chosen: datetime | None = None
        self.finished = False
        self.events: list[dict] = []  # өөрчлөлтүүд -> phone_server ажилтанд мэдэгдэнэ

    @property
    def now(self) -> datetime:
        return self._now or datetime.now(people.TZ)

    def dtmf_len(self) -> int:
        """Товчлуураар хэдэн цифр хүлээж байна (0 = товчлуур хэрэггүй)."""
        return {"code": people.CODE_LEN, "staff_code": people.STAFF_PIN_LEN, "target": people.CODE_LEN,
                "new_phone": 8}.get(self.state, 1)

    @property
    def source(self) -> str:
        return "staff" if self.staff else "ai"

    def _end(self) -> str:
        """Үйлдлийн дараах хэллэг: ажилтан дараагийн хүн рүү, залгагч "өөр асуулт байна уу"."""
        if self.staff:
            self.state, self.lead = "target", None
            return "staff_next"
        return "anything_else"

    # ---------- оролт ----------

    def handle_dtmf(self, digits: str) -> list[str] | None:
        if self.state == "staff_code":
            return self._staff_code(digits)
        if self.state == "target":
            found = people.find(self.tdir, digits)
            return self._candidates([found] if found else [], "")
        if self.state == "target_confirm":
            return self._target_confirm({"1": True, "2": False}.get(digits[:1]))
        if self.state == "code":
            return self._code(digits)
        if self.state == "new_phone":
            return self._phone(digits)
        if self.state in ("phone_confirm", "slot_confirm", "cancel_confirm", "reg_cancel_confirm"):
            return self._confirm({"1": True, "2": False}.get(digits[:1]))
        if self.state == "slot":
            i = int(digits[:1]) - 1 if digits[:1].isdigit() else -1
            return self._pick(i) if 0 <= i < len(self.offered) else ["slot_pick_again"]
        if self.state == "menu" and digits[:1] in MENU_KEYS:
            return self._do(MENU_KEYS[digits[:1]])
        return None

    def handle(self, text: str) -> list[str] | None:
        if self.state == "staff_code":
            digits = re.sub(r"\D", "", parse_phone(text))
            return self._staff_code(digits) if digits else None
        if self.state == "target":
            digits = re.sub(r"\D", "", parse_phone(text))
            if len(digits) == people.CODE_LEN:
                found = people.find(self.tdir, digits)
                return self._candidates([found] if found else [], "")
            return self._candidates(people.find_by_name(self.tdir, text), text)
        if self.state == "target_confirm":
            ans = yes_no(text)
            return self._target_confirm(ans) if ans is not None else ["confirm_target"]
        if self.state == "code":
            digits = re.sub(r"\D", "", parse_phone(text))
            return self._code(digits) if digits else None
        if self.state == "new_phone":
            digits = parse_phone(text)
            return self._phone(digits) if digits else ["ask_new_phone"]
        if self.state in ("phone_confirm", "slot_confirm", "cancel_confirm", "reg_cancel_confirm"):
            ans = yes_no(text)
            return self._confirm(ans) if ans is not None else ["confirm"]
        if self.state == "slot":
            i = self._ordinal(text)
            if i is not None and i < len(self.offered):
                return self._pick(i)
            return self._offer(text)          # "Баасан гаригт болох уу" -> шинэ сонголт
        # menu: хувийн баримтууд + хүсэлтүүдээс хайна
        if self.staff and people.find_by_name(self.tdir, text):    # ажилтан өөр хүний нэр хэлсэн
            self.state = "target"
            return self.handle(text)
        intent = self._retrieve(text)
        return self._do(intent, text) if intent else None

    # ---------- ажилтан ----------

    def _staff_code(self, digits: str) -> list[str]:
        if not people.check_staff_pin(self.tdir, digits):
            self.tries += 1
            if self.tries >= MAX_CODE_TRIES:
                self.finished = True
                return ["code_fail"]
            return ["code_wrong"]
        self.state, self.tries = "target", 0
        return ["staff_verified"]

    def _candidates(self, found: list[dict], text: str) -> list[str]:
        """Олдсон хүмүүсийн эхнийхийг кодоор нь уншиж баталгаажуулна (нэрийг TTS-гүйгээр хэлж чадахгүй)."""
        if not found:
            return ["target_not_found"]
        self.candidates = found
        self.command = people.strip_name(text, found[0].get("name") or "") if text else ""
        return self._read_target()

    def _read_target(self) -> list[str]:
        lead = self.candidates[0]
        self.state = "target_confirm"
        keys = ["target_is", f"digits:{people.ensure_code(self.tdir, lead['id'])}"]
        if lead.get("phone"):
            keys += ["target_phone", f"digits:{lead['phone']}"]
        return keys + ["confirm_target"]

    def _target_confirm(self, ans: bool | None) -> list[str]:
        if ans is None:
            return ["confirm_target"]
        if not ans:
            self.candidates = self.candidates[1:]
            if self.candidates:
                return self._read_target()
            self.state = "target"
            return ["target_not_found"]
        self.lead, self.state = self.candidates[0], "menu"
        people.docs(self.tdir, self.lead["id"])
        intent = detect_staff_intent(self.search, self.command) if self.command.strip() else None
        if intent:
            return self._do(intent, self.command)
        return self._appointment_keys() + ["menu"]

    # ---------- алхмууд ----------

    def _code(self, digits: str) -> list[str]:
        found = people.find(self.tdir, digits)
        if not found:
            self.tries += 1
            if self.tries >= MAX_CODE_TRIES:
                self.finished = True
                return ["code_fail"]
            return ["code_wrong"]
        self.lead = found
        people.docs(self.tdir, found["id"])
        self.state = "menu"
        keys = ["verified"]
        if self.intent and self.intent in INTENTS:
            return keys + self._do(self.intent)
        return keys + self._appointment_keys() + ["menu"]

    def _appointment_keys(self) -> list[str]:
        when = people.appointment(self.tdir, self.lead["id"])
        return ["appt_is", f"date:{people.fmt(when)}"] if when else ["no_appt"]

    def _retrieve(self, text: str) -> str | None:
        """Зөвхөн энэ хүний баримтууд (person_docs) + хүсэлтүүдээс хайна."""
        lead_id = self.lead["id"]
        docs = [(DOC_INTENT[d["field"]], d["text"]) for d in people.docs(self.tdir, lead_id) if d["field"] in DOC_INTENT]
        for d in people.docs(self.tdir, lead_id):     # шинэ/өөрчлөгдсөн баримтын векторыг хадгална
            if d["emb"] is None and d["field"] in DOC_INTENT:
                people.save_emb(self.tdir, lead_id, d["field"], d["text"], self.search.vectors([d["text"]])[0].tobytes())
        docs += [(k, q) for k, qs in INTENTS.items() for q in qs]
        ranked = self.search.rank(text, docs)
        kw = keyword_intent(text)
        if ranked and ranked[0][1] >= MATCH:
            top = ranked[0][0]
            return kw if kw in ("cancel", "cancel_registration") and top in ("cancel", "cancel_registration") else top
        return kw

    def _do(self, intent: str, text: str = "") -> list[str]:
        self.intent = None
        lead_id = self.lead["id"]
        if intent == "cancel_registration":
            if (people.lead(self.tdir, lead_id) or {}).get("status") == "canceled":
                return ["status_canceled", self._end()]
            self.state = "reg_cancel_confirm"
            return ["ask_cancel_reg"]
        if intent == "ask_attendance":
            coming = people.attendance(self.tdir, lead_id)
            self.state = "menu"
            return ["attendance_unknown" if coming is None else "attendance_yes" if coming else "attendance_no", self._end()]
        if intent == "change_phone":
            self.state = "new_phone"
            return ["ask_new_phone"]
        if intent == "change_time":
            return self._offer(text)
        if intent == "cancel":
            if not people.appointment(self.tdir, lead_id):
                return ["no_appt", self._end()]
            self.state = "cancel_confirm"
            return self._appointment_keys() + ["ask_cancel"]
        self.state = "menu"
        if intent == "ask_phone":
            phone = (people.lead(self.tdir, lead_id) or {}).get("phone")
            return (["phone_is", f"digits:{phone}"] if phone else ["no_phone"]) + [self._end()]
        if intent == "ask_status":
            status = (people.lead(self.tdir, lead_id) or {}).get("status") or "new"
            return [f"status_{status}" if status in people.STATUS_WORDS else "status_new", self._end()]
        return self._appointment_keys() + [self._end()]      # ask_time

    def _phone(self, digits: str) -> list[str]:
        local = digits[3:] if digits.startswith("976") and len(digits) == 11 else digits
        if len(local) != 8:
            return ["phone_retry"]
        self.new_phone, self.state = local, "phone_confirm"
        return ["new_phone_is", f"digits:{local}", "confirm"]

    def _offer(self, text: str) -> list[str]:
        """Сул цагуудаас санал болгоно. Залгагч өдөр/цаг хэлсэн бол хайлтаар хамгийн ойрыг."""
        free = people.free_slots(self.tdir, self.now, exclude_lead=self.lead["id"])
        if not free:
            self.state = "menu"
            return ["no_slots", self._end()]
        if text.strip():
            picks = self._match_slots(text, free)
        else:
            picks = free[:OFFER]
        self.offered, self.state = sorted(picks), "slot"
        keys = ["slots_intro"]
        for i, at in enumerate(self.offered):
            keys += [f"press_{i + 1}", f"date:{people.fmt(at)}"]
        return keys

    def _match_slots(self, text: str, free: list[datetime]) -> list[datetime]:
        """Сул цаг бүр нэг баримт: "маргааш Баасан гараг аравдугаар сарын арван долооны арван цагт"."""
        q = stems(text)
        wanted_day = {d for s, d in WEEKDAY_STEMS.items() if s in q}
        pool = [at for at in free if not wanted_day or at.weekday() in wanted_day] or free
        docs = [(i, f"{people.relative_words(at, self.now)} {people.slot_text(at)}") for i, at in enumerate(pool)]
        ranked = self.search.rank(text, docs)
        return [pool[i] for i, _ in ranked[:OFFER]]

    def _ordinal(self, text: str) -> int | None:
        for st in stems(text):
            for key, i in ORDINALS.items():
                if st.startswith(key) or key.startswith(st):
                    return i
        return None

    def _pick(self, i: int) -> list[str]:
        self.chosen, self.state = self.offered[i], "slot_confirm"
        return ["you_chose", f"date:{people.fmt(self.chosen)}", "confirm"]

    def _confirm(self, ans: bool | None) -> list[str]:
        if ans is None:
            return ["confirm"]
        lead_id, state = self.lead["id"], self.state
        self.state = "menu"
        if state == "phone_confirm":
            if not ans:
                self.state = "new_phone"
                return ["ask_new_phone"]
            old = people.set_phone(self.tdir, lead_id, self.new_phone, self.source, self.call_uuid)
            self.events.append({"field": "phone", "old": old, "new": self.new_phone, "lead": self.lead, "staff": self.staff})
            return ["phone_done", self._end()]
        if state == "slot_confirm":
            if not ans:
                return self._offer("")
            try:
                old = people.set_appointment(self.tdir, lead_id, self.chosen, self.source, self.call_uuid, now=self.now)
            except ValueError:                # яг энэ хооронд өөр хүн авсан
                return ["slot_taken"] + self._offer("")
            self.events.append({"field": "appointment", "old": old and people.fmt(old), "new": people.fmt(self.chosen),
                                "lead": self.lead, "staff": self.staff})
            return ["appt_done", f"date:{people.fmt(self.chosen)}", self._end()]
        if not ans:                           # cancel_confirm, reg_cancel_confirm
            return ["unchanged", self._end()]
        if state == "reg_cancel_confirm":
            old = people.cancel_registration(self.tdir, lead_id, self.source, self.call_uuid)
            self.events.append({"field": "status", "old": old, "new": "canceled", "lead": self.lead, "staff": self.staff})
            return ["reg_cancel_done", self._end()]
        old = people.cancel_appointment(self.tdir, lead_id, self.source, self.call_uuid)
        self.events.append({"field": "appointment", "old": old and people.fmt(old), "new": None, "lead": self.lead,
                            "staff": self.staff})
        return ["cancel_done", self._end()]
