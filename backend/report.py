"""
Нэмэлт (SIM-TRUNK-д алга): долоо хоногийн тайлан — Даваа гараг бүр 09:00-д байгууллагын Telegram групп руу.

  дуудлага, хариулсан хувь, хамгийн их асуусан сэдэв (FAQ / мэдээллийн "## гарчиг"), хариулж чадаагүй
  давтагдсан асуулт, шинэ бүртгэл, AI сануулгын үр дүн, хамгийн ачаалалтай цаг
Сэдвийг AI-ийн хариултаас тодорхойлно: хариулт бүр байгууллагын FAQ эсвэл мэдээллийн өгүүлбэр (зохиодоггүй).
"""
import json
import os
import re
import threading
import time
from collections import Counter
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import db
from tenant import Tenant, all_tenants

TZ = ZoneInfo("Asia/Ulaanbaatar")
TOPIC_ROUTES = {"faq", "faq_near", "fact", "fact2", "llm", "model", "en_faq", "en_fact"}
SEND_DAY, SEND_HOUR = 0, 9          # Даваа 09:00
FILLER = {"а", "аа", "ээ", "өө", "м", "байна", "уу", "үү", "алло", "сайн", "за", "тийм", "үгүй", "мэдээлэл", "юу", "би"}


def meaningful(q: str) -> bool:
    """Чимээ, "байна уу", "а а а" гэх мэтийг тайланд оруулахгүй."""
    words = _norm(q).split()
    return len("".join(words)) >= 6 and any(w not in FILLER for w in words)


def _load(path: str, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def _norm(q: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s]", " ", q.lower())).strip()


def build(t: Tenant, days: int = 7, now: float | None = None) -> dict:
    now = now or time.time()
    since = now - days * 86400
    faq = {x["answer"]: (x.get("questions") or [x["id"]])[0] for x in _load(t.faq_path, {}).get("faq", [])}
    facts = {x["text"]: x.get("section") or "Мэдээлэл" for x in _load(os.path.join(t.kb_index_dir, "facts.json"), {}).get("facts", [])}
    topics, hours = Counter(), Counter()
    with db.connect(t.db_path) as con:
        calls = con.execute("SELECT started_at FROM calls WHERE started_at >= ? AND started_at < ?", (since, now)).fetchall()
        asked = con.execute("SELECT COUNT(*) FROM messages WHERE role='user' AND ts >= ? AND ts < ?", (since, now)).fetchone()[0]
        answers = con.execute("SELECT text, route FROM messages WHERE role='assistant' AND ts >= ? AND ts < ?",
                              (since, now)).fetchall()
        placeholders = ",".join("?" * len(db.UNANSWERED_ROUTES))
        failed = con.execute(f"""
            SELECT u.text FROM messages a JOIN messages u ON u.id = (
                SELECT MAX(id) FROM messages WHERE call_uuid=a.call_uuid AND role='user' AND id < a.id)
            WHERE a.role='assistant' AND a.route IN ({placeholders}) AND a.ts >= ? AND a.ts < ?""",
                             (*db.UNANSWERED_ROUTES, since, now)).fetchall()
        new_leads = con.execute("SELECT COUNT(*) FROM leads WHERE created_at >= ? AND created_at < ?", (since, now)).fetchone()[0]
    for (started,) in calls:
        hours[datetime.fromtimestamp(started, TZ).hour] += 1
    answered = 0
    for text, route in answers:
        route = route or ""
        if route.startswith("lead_") or route == "greeting":
            continue
        if route in db.UNANSWERED_ROUTES:
            continue
        answered += 1
        if route in TOPIC_ROUTES:
            label = faq.get(text) or facts.get(text) or next((facts[s] for s in facts if s in text), None) or "Бусад"
            topics[label] += 1
    unanswered = len(failed)
    groups: dict[str, list[str]] = {}
    hidden = set(_load(t.path("data", "unanswered_hidden.json"), []))     # "Хариулж чадаагүй"-д нуусан
    from routes.unanswered import clean_question          # stt.clean (гацалт) + байгууллагын stt_fixes
    for (q,) in failed:
        if q and q.strip() and q.strip() not in hidden:
            q = clean_question(t, q.strip())
            if meaningful(q):
                groups.setdefault(_norm(q), []).append(q)
    top_failed = sorted(groups.values(), key=len, reverse=True)[:5]
    rem = Counter()
    for item in _load(t.path("data", "reminders.json"), {}).get("items", {}).values():
        for h in item.get("history", []):
            if since <= h.get("ts", 0) < now:
                rem[h["outcome"]] += 1
    total = answered + unanswered
    peak = hours.most_common(1)[0][0] if hours else None
    return {"days": days, "from": since, "to": now, "calls": len(calls), "questions": asked, "answered": answered,
            "unanswered": unanswered, "rate": round(100 * answered / total) if total else None,
            "topics": topics.most_common(5), "unanswered_top": [{"q": g[0], "count": len(g)} for g in top_failed],
            "new_leads": new_leads, "reminders": dict(rem), "peak_hour": peak}


def text(t: Tenant, r: dict) -> str:
    d1 = datetime.fromtimestamp(r["from"], TZ).strftime("%m.%d")
    d2 = datetime.fromtimestamp(r["to"] - 1, TZ).strftime("%m.%d")
    name = t.config().get("name", t.slug)
    lines = [f"📊 {name} — {r['days']} хоногийн тайлан ({d1}–{d2})"]
    if not r["calls"]:
        return "\n".join(lines + ["Энэ хугацаанд дуудлага ирээгүй."])
    rate = f" · хариулсан {r['rate']}% ({r['answered']}/{r['answered'] + r['unanswered']})" if r["rate"] is not None else ""
    lines.append(f"📞 Дуудлага: {r['calls']} · асуулт {r['questions']}{rate}")
    if r["topics"]:
        lines.append("🔝 Их асуусан: " + ", ".join(f"{label} ({n})" for label, n in r["topics"]))
    if r["unanswered_top"]:
        lines.append("❓ Хариулж чадаагүй: " + "; ".join(f"«{x['q'][:60]}»" + (f" ×{x['count']}" if x["count"] > 1 else "")
                                                       for x in r["unanswered_top"]))
        lines.append("   → вэб «Хариулж чадаагүй» хэсэгт хариулт заавал AI дараагийн удаа хариулна")
    rem = r["reminders"]
    parts = [f"шинэ бүртгэл {r['new_leads']}"]
    if rem:
        parts.append("AI сануулга " + " ".join(f"{icon} {rem[k]}" for k, icon in
                                               (("confirmed", "✅"), ("declined", "❌"), ("no_answer", "📵"), ("busy", "📵"),
                                                ("unconfirmed", "❔")) if rem.get(k)))
    lines.append("🧾 " + " · ".join(parts))
    if r["peak_hour"] is not None:
        lines.append(f"⏰ Хамгийн ачаалалтай цаг: {r['peak_hour']:02d}:00–{(r['peak_hour'] + 1) % 24:02d}:00")
    return "\n".join(lines)


def enabled(t: Tenant) -> bool:
    import notify
    return notify.load_settings(t).get("weekly_report", True)


def send(t: Tenant, now: float | None = None) -> bool:
    import notify
    ok = notify.send(t, text(t, build(t, 7, now)))
    if ok:
        st = notify.load_settings(t)
        st["weekly_report_sent"] = int(now or time.time())
        notify.save_settings(t, st)
    return ok


def due(t: Tenant, now: float) -> bool:
    """Даваа 09:00-аас хойш, энэ долоо хоногт илгээгээгүй, Telegram тохируулсан, асаалттай."""
    import notify
    st = notify.load_settings(t)
    if not (st.get("telegram_token") and st.get("telegram_chat_id")) or not st.get("weekly_report", True):
        return False
    local = datetime.fromtimestamp(now, TZ)
    week_start = (local - timedelta(days=(local.weekday() - SEND_DAY) % 7)).replace(hour=SEND_HOUR, minute=0, second=0,
                                                                                  microsecond=0)
    return local >= week_start and st.get("weekly_report_sent", 0) < week_start.timestamp()


def send_due(now: float | None = None) -> list[str]:
    now = now or time.time()
    return [t.slug for t in all_tenants() if due(t, now) and send(t, now)]


def _loop():
    while True:
        time.sleep(600)
        try:
            send_due()
        except Exception as exc:
            print(f"  [тайлан] {exc}")


if os.getenv("REPORT_SCHEDULER", "1") == "1":
    threading.Thread(target=_loop, daemon=True).start()
