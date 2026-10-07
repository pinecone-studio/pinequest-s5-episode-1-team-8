# AI runtime

Энэ хавтас нь утасны AI engine, RAG/FAQ индекс, selector сургалт, STT/TTS болон
SIP bridge-ийн кодыг агуулна. Эдгээр файл энэ repository-д хадгалагддаг тул
ажиллуулахад тусдаа `SIM-TRUNK` repository хэрэггүй.

Өгөгдөл, индекс, аудио болон нууц түлхүүрийг энд commit хийхгүй. Бүгд
`backend/data/` дотор хадгалагдаж, `backend/knowledge_jobs.py` runtime үүсгэхдээ
энэ кодтой холбоно.

- `phone_server.py` — AudioSocket AI сервер
- `sip_bridge.py` — SIP/RTP bridge
- `stream_voice.py` — RAG routing, TTS болон ярианы урсгал
- `account.py`, `people.py` — хэрэглэгчийн мэдээлэл шалгах/солих үйлдэл
- `scripts/` — мэдээлэл ingest, англи аудио, selector сургалт, чанарын шалгалт

Python сангуудын хувилбар `backend/requirements.txt`-д бий.

Үйлдлийн хурдан тест:

```bash
.venv/bin/python backend/ai_runtime/test_account.py
```
