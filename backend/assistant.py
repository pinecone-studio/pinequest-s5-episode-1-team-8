"""
AI туслах: хүн өөрийн бүртгэлийг (хувийн RAG, people.py) ярьж/товчлуураар шалгаж, өөрчилнө.

  Залгагч: "Эвентэд очиж чадахгүй боллоо" -> "Бүртгэлийн кодоо бичнэ үү" -> код
     -> зөвхөн ТЭР хүний баримтуудаас (person_docs) хайна -> бүртгэл цуцлах / цаг солих / дугаар солих / асуух
     -> "Тийм бол нэг" гэж баталсны дараа л өгөгдлийн санд бичнэ -> баримт шинэчлэгдэнэ -> ажилтанд мэдэгдэл
  Ажилтан (багш): ажилтны код -> "Болдын цагийг Баасан руу шилжүүл" -> БҮХ хүний баримтаас нэрээр хайна
     -> кодыг нь уншиж батлуулна -> гүйцэтгэнэ -> дараагийн хүн

AI SQL бичихгүй, шинэ мэдээлэл зохиохгүй: зөвхөн people.py-ийн тогтмол үйлдлүүдээс сонгоно.
handle(text) / handle_dtmf(digits) -> хариултын түлхүүрүүд (render() текст болгоно):
  "<хэллэг>"                 tenant.phrases()["account"][key]
  "digits:99112233"          дугаар/кодыг цифрээр
  "date:2026-10-17T10:00"    гараг, сар, өдөр, цаг
  "doc:course"               хүний бүртгэлийн утга (хөтөлбөр, эвент)
  None -> энэ нь урсгалын хариулт биш (шинэ асуулт)
"""
import re
from datetime import datetime

import numpy as np

import embedder
import people
from speech_parse import parse_phone, yes_no

MAX_CODE_TRIES = 3
# Хайлтын доод оноо: bge-m3 — хүсэлтүүд >= 0.90, ерөнхий асуулт <= 0.80; char-ngram — тестээр тааруулсан
MATCH = 0.85 if embedder.MODEL == "bge-m3" else 0.70   # char: хүсэлт >= 0.87, ерөнхий асуулт <= 0.58 (test_assistant)
LEX_WEIGHT = 0.15
OFFER = 3

INTENTS = {
    "cancel_registration": ["Бүртгэлээ цуцлах", "Бүртгэлээ цуцалмаар байна", "Эвентэд очиж чадахгүй боллоо", "Хөтөлбөрт суухаа больсон",
                            "Оролцож чадахгүй нь", "Ирж чадахгүй нь цуцалъя", "Бүртгэлээ буцаая", "Явахгүй болсон"],
    "change_phone": ["Дугаараа солимоор байна", "Утасны дугаараа өөрчлөх", "Шинэ дугаар өгье", "Дугаар солих",
                     "Дугаар маань солигдсон"],
    "change_time": ["Цагаа солимоор байна", "Өөр цаг авъя", "Уулзалтын цагаа хойшлуулах", "Цагаа өөрчлөх",
                    "Өөр өдөр болох уу", "Цагаа шилжүүлэх"],
    "cancel": ["Цагаа цуцлах", "Уулзалтаа цуцалмаар байна", "Товлосон цагаа цуцлах"],
    "ask_time": ["Миний цаг хэзээ билээ", "Хэдэн цагт очих вэ", "Уулзалт хэзээ вэ", "Хэдний өдөр очих вэ"],
    "ask_phone": ["Ямар дугаар бүртгэлтэй вэ", "Миний дугаар зөв үү", "Бүртгэлтэй дугаараа шалгах"],
    "ask_status": ["Бүртгэл маань ямар байгаа вэ", "Бүртгэл баталгаажсан уу", "Хүсэлт маань хаана явж байна"],
    "ask_course": ["Би юунд бүртгүүлсэн бэ", "Ямар хөтөлбөрт бүртгүүлсэн бэ", "Ямар эвентэд бүртгүүлсэн бэ"],
    "ask_attendance": ["Эвентэд ирэх эсэх маань бүртгэгдсэн үү", "Ирнэ гэж бүртгэгдсэн үү", "Намайг ирнэ гэж тэмдэглэсэн үү",
                       "Ирэх эсэхээ шалгах"],
}
STAFF_INTENTS = {
    "cancel_registration": ["бүртгэлийг нь цуцал", "хөтөлбөрөөс хас", "эвентээс хас", "ирэхгүй гэсэн"],
    "change_phone": ["дугаарыг нь солих", "утасны дугаарыг нь өөрчил", "шинэ дугаар оруул"],
    "change_time": ["цагийг нь шилжүүл", "цагийг нь солих", "өөр өдөр рүү шилжүүл", "уулзалтыг нь хойшлуул",
                    "руу шилжүүл"],
    "cancel": ["цагийг нь цуцал", "уулзалтыг нь цуцлах"],
    "ask_time": ["цаг нь хэзээ вэ", "хэдэн цагт ирэх вэ"],
    "ask_phone": ["дугаар нь хэд вэ", "ямар дугаартай вэ"],
    "ask_status": ["бүртгэл нь ямар байгаа вэ", "төлөв нь юу вэ"],
    "ask_course": ["юунд бүртгүүлсэн бэ", "ямар хөтөлбөр вэ"],
    "ask_attendance": ["ирэх үү", "ирнэ гэсэн үү", "ирэх эсэх нь"],
}
INTENT_LABELS = {"cancel_registration": "бүртгэл цуцлах", "change_phone": "дугаар солих", "change_time": "цаг солих",
                 "cancel": "цаг цуцлах", "ask_time": "цагаа асуух", "ask_phone": "дугаараа асуух",
                 "ask_status": "төлөв асуух", "ask_course": "бүртгэлээ асуух", "ask_attendance": "ирэх эсэхээ асуух"}
DOC_INTENT = {"phone": "ask_phone", "appointment": "ask_time", "status": "ask_status", "course": "ask_course",
              "attendance": "ask_attendance"}
MENU_KEYS = {"1": "change_phone", "2": "change_time", "3": "cancel", "4": "cancel_registration"}
ORDINALS = {"нэг": 0, "эхн": 0, "хоёр": 1, "гура": 2, "гурв": 2, "сүүл": 2}
WEEKDAY_STEMS = {"дава": 0, "мягм": 1, "лхаг": 2, "пүрэ": 3, "пүрв": 3, "баас": 4, "бямб": 5, "ням": 6}
CHANGE_STEMS = ("шилж", "соли", "солъ", "соль", "өөрч", "хойш", "урагш")
CANT_GO = ("чадах", "больс", "явах", "суух", "оролц", "ирэхг", "очихг")


def stems(text: str) -> set[str]:
    return {w[:4] for w in re.findall(r"[а-яөүёa-z0-9]+", text.lower()) if len(w) >= 2}


class Search:
    """RAG-ийн хайлт (embedder.embed). last — сүүлийн хайлтын эхний үр дүнгүүд (вэбд харуулна)."""

    def __init__(self, embed=embedder.embed):
        self.embed = embed
        self.cache: dict[str, np.ndarray] = {}
        self.last: list[dict] = []

    def vectors(self, texts: list[str]) -> np.ndarray:
        todo = [t for t in dict.fromkeys(texts) if t not in self.cache]
        if todo:
            for t, v in zip(todo, self.embed(todo)):
                self.cache[t] = np.asarray(v, np.float32)
        return np.stack([self.cache[t] for t in texts])

    def rank(self, query: str, docs: list[tuple[object, str]], kind: str = "") -> list[tuple[object, float]]:
        if not docs:
            return []
        sims = self.vectors([t for _, t in docs]) @ self.vectors([query])[0]
        qs = stems(query)
        best: dict = {}
        text_of: dict = {}
        for (key, text), s in zip(docs, sims):
            score = float(s) + (LEX_WEIGHT * len(qs & stems(text)) / len(qs) if qs else 0.0)
            if score > best.get(key, -1.0):
                best[key], text_of[key] = score, text
        ranked = sorted(best.items(), key=lambda x: -x[1])
        self.last = [{"kind": kind, "key": str(k), "text": text_of[k], "score": round(s, 3)} for k, s in ranked[:5]]
        return ranked


def keyword_intent(text: str) -> str | None:
    """Богино команд үгээр (вектор босгонд хүрээгүй үед)."""
    st = stems(text)
    low = text.lower()
    reg = any(x.startswith(("бүрт", "хөтө", "эвен", "сурга", "boot")) for x in st)
    if any(x.startswith("цуца") for x in st):
        return "cancel_registration" if reg or not any(x.startswith(("цаг", "уулз")) for x in st) else "cancel"
    if any(c in low for c in CANT_GO) and any(x.startswith(("чада", "боло", "боль")) for x in st):
        return "cancel_registration"
    if any(x.startswith(CHANGE_STEMS) for x in st):
        if any(x.startswith(("дуга", "утас", "утсы")) for x in st):
            return "change_phone"
        return "change_time"
    return None


def detect_intent(search: Search, text: str, staff: bool = False) -> str | None:
    sources = (STAFF_INTENTS, INTENTS) if staff else (INTENTS,)
    ranked = search.rank(text, [(k, q) for src in sources for k, qs in src.items() for q in qs], "хүсэлт")
    return _choose(ranked, text)


def _choose(ranked: list, text: str) -> str | None:
    """Векторын хайлт + түлхүүр үг: "цуцлах" үед бүртгэл/цагийг үгээр нь ялгана ("Бүртгэлээ цуцал" ≠ "Цагаа цуцал")."""
    kw = keyword_intent(text)
    if ranked and ranked[0][1] >= MATCH:
        top = ranked[0][0]
        if top in DOC_INTENT.values() or top in INTENTS:
            if kw in ("cancel", "cancel_registration") and top in ("cancel", "cancel_registration"):
                return kw
            return top
    return kw


class AccountFlow:
    def __init__(self, tdir: str, search: Search, intent: str | None = None, call_uuid: str | None = None,
                 now: datetime | None = None, staff: bool = False):
        self.tdir, self.search, self.intent, self.call_uuid = tdir, search, intent, call_uuid
        self._now = now
        self.staff = staff
        # code | staff_code | target | target_confirm | menu | new_phone | phone_confirm | slot | slot_confirm
        # | cancel_confirm | reg_cancel_confirm
        self.state = "staff_code" if staff else "code"
        self.candidates: list[dict] = []
        self.command = ""
        self.lead: dict | None = None
        self.tries = 0
        self.new_phone = None
        self.offered: list[datetime] = []
        self.chosen: datetime | None = None
        self.finished = False
        self.events: list[dict] = []

    @property
    def now(self) -> datetime:
        return self._now or datetime.now(people.TZ)

    @property
    def source(self) -> str:
        return "staff" if self.staff else "ai"

    def dtmf_len(self) -> int:
        return {"code": people.CODE_LEN, "staff_code": people.STAFF_PIN_LEN, "target": people.CODE_LEN,
                "new_phone": 8}.get(self.state, 1)

    def _end(self) -> str:
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
        if self.state == "staff_code":           # кодгүй бол ажилтны горимоос гаргахгүй, дахин асууна
            digits = re.sub(r"\D", "", parse_phone(text))
            return self._staff_code(digits) if digits else ["staff_ask_pin"]
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
            return self._offer(text)
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
        if not found:
            return ["target_not_found"]
        self.candidates = found
        self.command = people.strip_name(text, found[0].get("name") or "") if text else ""
        self.search.last = [{"kind": "хүн", "key": str(x["id"]), "text": f"{x.get('name') or '—'} · {x.get('course') or ''}",
                             "score": round(people.name_score(text, x.get("name") or ""), 3) if text else 1.0}
                            for x in found[:5]]
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
        intent = detect_intent(self.search, self.command, staff=True) if self.command.strip() else None
        if intent:
            return self._do(intent, self.command)
        return self._appointment_keys() + ["menu"]

    # ---------- залгагч ----------

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
        rows = people.docs(self.tdir, lead_id)
        docs = [(DOC_INTENT[d["field"]], d["text"]) for d in rows if d["field"] in DOC_INTENT]
        for d in rows:                       # шинэ/өөрчлөгдсөн баримтын векторыг DB-д хадгална
            if d["emb"] is None:
                people.save_emb(self.tdir, lead_id, d["field"], d["text"], self.search.vectors([d["text"]])[0].tobytes())
        sources = (STAFF_INTENTS, INTENTS) if self.staff else (INTENTS,)
        docs += [(k, q) for src in sources for k, qs in src.items() for q in qs]
        ranked = self.search.rank(text, docs, "хувийн баримт")
        return _choose(ranked, text)

    def _do(self, intent: str, text: str = "") -> list[str]:
        self.intent = None
        lead_id = self.lead["id"]
        lead = people.lead(self.tdir, lead_id) or {}
        if intent == "cancel_registration":
            if lead.get("status") == "canceled":
                return ["status_canceled", self._end()]
            self.state = "reg_cancel_confirm"
            return (["course_is", "doc:course"] if lead.get("course") else []) + ["ask_cancel_reg"]
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
            return (["phone_is", f"digits:{lead['phone']}"] if lead.get("phone") else ["no_phone"]) + [self._end()]
        if intent == "ask_status":
            status = lead.get("status") or "new"
            return [f"status_{status}" if status in people.STATUS_WORDS else "status_new", self._end()]
        if intent == "ask_attendance":
            coming = people.attendance(self.tdir, lead_id)
            key = "attendance_unknown" if coming is None else "attendance_yes" if coming else "attendance_no"
            return [key, self._end()]
        if intent == "ask_course":
            return (["course_is", "doc:course"] if lead.get("course") else ["no_course"]) + [self._end()]
        return self._appointment_keys() + [self._end()]      # ask_time

    def _phone(self, digits: str) -> list[str]:
        local = digits[3:] if digits.startswith("976") and len(digits) == 11 else digits
        if len(local) != 8:
            return ["phone_retry"]
        self.new_phone, self.state = local, "phone_confirm"
        return ["new_phone_is", f"digits:{local}", "confirm"]

    def _offer(self, text: str) -> list[str]:
        free = people.free_slots(self.tdir, self.now, exclude_lead=self.lead["id"])
        if not free:
            self.state = "menu"
            return ["no_slots", self._end()]
        picks = self._match_slots(text, free) if text.strip() else free[:OFFER]
        self.offered, self.state = sorted(picks), "slot"
        keys = ["slots_intro"]
        for i, at in enumerate(self.offered):
            keys += [f"press_{i + 1}", f"date:{people.fmt(at)}"]
        return keys

    def _match_slots(self, text: str, free: list[datetime]) -> list[datetime]:
        q = stems(text)
        wanted_day = {d for s, d in WEEKDAY_STEMS.items() if s in q}
        pool = [at for at in free if not wanted_day or at.weekday() in wanted_day] or free
        docs = [(i, f"{people.relative_words(at, self.now)} {people.slot_text(at)}") for i, at in enumerate(pool)]
        ranked = self.search.rank(text, docs, "сул цаг")
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

    def _event(self, field: str, old, new):
        self.events.append({"field": field, "old": old, "new": new, "lead": self.lead, "staff": self.staff})

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
            self._event("phone", old, self.new_phone)
            return ["phone_done", self._end()]
        if state == "slot_confirm":
            if not ans:
                return self._offer("")
            try:
                old = people.set_appointment(self.tdir, lead_id, self.chosen, self.source, self.call_uuid, now=self.now)
            except ValueError:
                return ["slot_taken"] + self._offer("")
            self._event("appointment", old and people.fmt(old), people.fmt(self.chosen))
            return ["appt_done", f"date:{people.fmt(self.chosen)}", self._end()]
        if not ans:
            return ["unchanged", self._end()]
        if state == "reg_cancel_confirm":
            old = people.cancel_registration(self.tdir, lead_id, self.source, self.call_uuid)
            self._event("status", old, "canceled")
            return ["reg_cancel_done", self._end()]
        old = people.cancel_appointment(self.tdir, lead_id, self.source, self.call_uuid)
        self._event("appointment", old and people.fmt(old), None)
        return ["cancel_done", self._end()]


def render(phrases: dict, lead: dict | None, keys: list[str], staff: bool = False) -> list[str]:
    """Түлхүүрүүд -> вэбд харуулах өгүүлбэрүүд (утсанд эдгээр нь бэлэн аудио клипүүд).
    Ажилтанд гуравдагч биеэр: "Таны бүртгэл цуцлагдсан" -> "Түүний бүртгэл цуцлагдсан"."""
    out = []
    for key in keys:
        if key.startswith("digits:"):
            d = key.split(":", 1)[1]
            out.append(" ".join(d[i:i + 2] for i in range(0, len(d), 2)))
        elif key.startswith("date:"):
            out.append(people.slot_text(people.parse_local(key.split(":", 1)[1])))
        elif key.startswith("doc:"):
            out.append(str((lead or {}).get(key.split(":", 1)[1]) or "—"))
        else:
            text = phrases.get(key, key)
            if staff and key not in ("staff_ask_pin", "staff_verified", "staff_next", "target_is", "target_phone",
                                     "confirm_target", "target_not_found"):
                text = re.sub(r"\bТаны\b", "Түүний", re.sub(r"\bТанд\b", "Түүнд", text))
            out.append(text)
    # "Таны уулзалтын цаг" + "Пүрэв гараг ..." -> нэг өгүүлбэр
    joined, buf = [], []
    for i, (key, text) in enumerate(zip(keys, out)):
        buf.append(text)
        nxt = keys[i + 1] if i + 1 < len(keys) else ""
        if not (key in ("appt_is", "phone_is", "target_is", "target_phone", "new_phone_is", "you_chose", "appt_done",
                        "course_is", "your_code") or key.startswith("press_") or nxt == "target_phone"):
            joined.append(" ".join(buf))
            buf = []
    if buf:
        joined.append(" ".join(buf))
    return joined
