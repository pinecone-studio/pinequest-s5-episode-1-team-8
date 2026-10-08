# pinequest-s5-episode-1-team-8

Монгол утасны AI ресепшн — вэб удирдлага. `backend/` (Python FastAPI) + `frontend/` (Next.js, bun).
Утасны AI/RAG runtime нь `backend/ai_runtime/` дотор багтсан; тусдаа SIM-TRUNK хавтас шаардахгүй.

## Ажиллуулах

Анх удаа нэг удаа:
```bash
uv venv --python 3.12 .venv
```

Дараа нь backend, frontend хоёуланг нь зэрэг:
```bash
./dev.sh          # http://localhost:3000   (унтраах: Ctrl+C)
```

Утаснаас SIP softphone-оор AI-тай ярьж туршихдаа бүх үйлчилгээг нэг командаар:
```bash
./dev.sh --phone  # веб + API + AudioSocket AI + SIP
```

`dev.sh` асах бүрдээ шинэ нэмэгдсэн (хөнгөн) сангуудыг автоматаар суулгана. «Аудио бэлдэх», AI сургалт, утасны AI-д
хэрэгтэй хүнд AI сангуудыг (torch, Whisper, bge-m3 — ~3GB) нэг удаа `./dev.sh --ai`-аар суулгана. Анх асахад `admin`-ийн нууц үг терминалд нэг удаа хэвлэгдэнэ.
Жишээ дуудлага: `.venv/bin/python backend/demo_data.py`

Дэлгэрэнгүй: [backend/README.md](backend/README.md), [frontend/README.md](frontend/README.md)
