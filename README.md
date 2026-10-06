# pinequest-s5-episode-1-team-8

Монгол утасны AI ресепшн — вэб удирдлага ба сервер тал.

| Хавтас | Юу вэ |
|---|---|
| [`backend/`](backend/README.md) | Python FastAPI сервер (порт 8100) — нэвтрэлт, API |
| [`frontend/`](frontend/README.md) | Next.js (bun) вэб удирдлага (порт 3000) — `/api/*` хүсэлтийг backend руу дамжуулна |

## Ажиллуулах

Анх удаа нэг удаа:
```bash
uv venv --python 3.12 .venv
```

Дараа нь backend, frontend хоёуланг нь зэрэг:
```bash
./dev.sh          # http://localhost:3000   (унтраах: Ctrl+C)
```

`dev.sh` асах бүрдээ шинэ нэмэгдсэн сангуудыг автоматаар суулгана. Анх асахад `admin`-ийн нууц үг терминалд нэг удаа хэвлэгдэнэ.
Жишээ дуудлага: `.venv/bin/python backend/demo_data.py`

Дэлгэрэнгүй: [backend/README.md](backend/README.md), [frontend/README.md](frontend/README.md)
