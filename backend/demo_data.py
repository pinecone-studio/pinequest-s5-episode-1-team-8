"""
Жишээ дуудлага, бүртгэл үүсгэнэ — утасны AI хэсэг бэлэн болохоос өмнө вэбийг хөгжүүлж, турших зорилгоор.

  .venv/bin/python backend/demo_data.py            # Pinecone (жишиг байгууллага)
  .venv/bin/python backend/demo_data.py <slug>     # өөр байгууллага

Дахин ажиллуулбал дахин нэмнэ (uuid нь demo-...). Сүүлийн 5 өдөрт тархсан.
"""
import os
import sys
import time
import uuid

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import db  # noqa: E402
import tenant as tenants  # noqa: E402

DAY = 86400
# (хэдэн өдрийн өмнө, залгагч, [(хэн, текст, route)], бүртгэл)
CALLS = [
    (0, "99112233", [("user", "Сайн байна уу", None), ("assistant", "Сайн байна уу. Та юуны талаар мэдэхийг хүсэж байна вэ?", "faq"),
                     ("user", "Software Engineer сургалт хэдэн сар вэ", None),
                     ("assistant", "Software Engineer хөтөлбөр 6 сар үргэлжилнэ.", "model"),
                     ("user", "Төлбөр хэд вэ", None), ("assistant", "Сургалтын төлбөр сард 1,500,000 төгрөг.", "fact")], None),
    (0, "88001122", [("user", "Хаана байрладаг вэ", None), ("assistant", "Манай хаяг: Сүхбаатар дүүрэг, Central Tower.", "faq"),
                     ("user", "Машины зогсоол бий юу", None),
                     ("assistant", "Уучлаарай, сайн ойлгосонгүй. Та дахин хэлж өгнө үү?", "repeat")], None),
    (1, "95554433", [("user", "Бүртгүүлмээр байна", None), ("assistant", "Бүртгэлд тань туслъя. Таны нэрийг хэлж өгнө үү?", "faq"),
                     ("user", "Болд", None), ("assistant", "Тантай холбогдох утасны дугаараа хэлж өгнө үү.", "lead_ask_phone"),
                     ("user", "ерэн тав тав тав дөчин гурав гучин гурав", None),
                     ("assistant", "Таны мэдээллийг амжилттай бүртгэлээ.", "lead_done")],
     {"name": "Болд", "phone": "95554433", "phone_raw": "ерэн тав тав тав дөчин гурав гучин гурав", "reason": "lead"}),
    (2, "80112233", [("user", "Хүүхдэд зориулсан сургалт байгаа юу", None),
                     ("assistant", "Энэ мэдээллийг баталгаатай олж чадсангүй. Манай ажилтан тан руу эргэж холбогдох уу?", "handoff"),
                     ("user", "Тийм", None), ("assistant", "За, манай ажилтан тан руу эргэж залгана. Таны нэрийг хэлж өгнө үү?", "faq"),
                     ("user", "Сарнай", None), ("assistant", "Таны нэрийг бүртгэлээ.", "lead_done")],
     {"name": "Сарнай", "phone": None, "phone_raw": "найм тэг", "reason": "handoff",
      "question": "Хүүхдэд зориулсан сургалт байгаа юу"}),
    (3, "99887766", [("user", "Мэдээлэл авъя", None),
                     ("assistant", "Та юуны талаар мэдэхийг хүсэж байна вэ? Жишээ нь сургалт, төлбөр эсвэл хуваарь.", "clarify"),
                     ("user", "Хичээл хэдэн цагаас эхэлдэг вэ", None),
                     ("assistant", "Хичээл өдөр бүр 9 цагаас эхэлнэ.", "fact")], None),
    (4, None, [("user", "Баярлалаа", None), ("assistant", "Зүгээр зүгээр. Өөр асуух зүйл байна уу?", "faq")], None),
]


def seed(t: tenants.Tenant) -> int:
    now = time.time()
    for i_call, (days, caller, msgs, lead) in enumerate(CALLS):
        cid = f"demo-{uuid.uuid4().hex[:12]}"
        ts = now - days * DAY - 3600 - i_call * 600      # ижил өдрийнх ч дараалал тодорхой
        db.start_call(t.db_path, cid, caller, ts=ts)
        for i, (role, text, route) in enumerate(msgs):
            user = role == "user"
            db.add_message(t.db_path, cid, role, text, route, score=None if user else 0.82,
                           stt_sec=0.6 if user else None, latency=None if user else 1.2, ts=ts + 4 * i + 2)
        if lead:
            db.add_lead(t.db_path, cid, lead["name"], lead["phone"], lead["phone_raw"], caller,
                        lead["reason"], lead.get("question"), ts=ts + 4 * len(msgs))
        db.end_call(t.db_path, cid, ts=ts + 4 * len(msgs) + 3)
    return len(CALLS)


if __name__ == "__main__":
    t = tenants.Tenant(sys.argv[1]) if len(sys.argv) > 1 else tenants.ensure_default()
    if not t.exists():
        raise SystemExit(f"Байгууллага олдсонгүй: {t.slug}")
    print(f"{t.slug}: {seed(t)} жишээ дуудлага нэмлээ")
