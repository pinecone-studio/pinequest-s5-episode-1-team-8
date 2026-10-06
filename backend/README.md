# Backend (Python FastAPI)

AI ресепшний сервер тал. Одоогоор зөвхөн **нэвтрэлт**. Вэб интерфейс нь `frontend/` (Next.js) — хөтөч backend руу шууд биш, Next.js-ээр дамжиж хандана.

## Суулгах, ажиллуулах

```bash
uv venv --python 3.12 .venv
uv pip install --python .venv/bin/python -r backend/requirements.txt

.venv/bin/python backend/app.py        # http://127.0.0.1:8100
```

Анх асахад хэрэглэгч байхгүй бол `admin` хэрэглэгч санамсаргүй нууц үгтэй үүсч, терминалд **нэг удаа** хэвлэгдэнэ.
Нууц үг солих: `.venv/bin/python backend/accounts.py admin admin`

Порт 8100 (SIM-TRUNK-ийн вэб 8000 дээр ажилладаг тул давхцахгүй). Солих: `API_PORT=...`

## API

| Хүсэлт | Юу хийх вэ |
|---|---|
| `POST /api/login` `{"email", "password"}` | Зөв бол хэрэглэгч + httpOnly session cookie (`pc_session`, 7 хоног) |
| `POST /api/logout` | Cookie устгана |
| `GET /api/me` | Нэвтэрсэн хэрэглэгч `{email, role, tenant, expires}`, үгүй бол 401 |

Бусад бүх `/api/*` нэвтрэлт шаардана (middleware). `/docs` хаалттай.

## Файлууд

| Файл | Үүрэг |
|---|---|
| `app.py` | FastAPI: нэвтрэх, гарах, `/api/me`, нэвтрэлт шалгах middleware |
| `accounts.py` | Хэрэглэгчид (SQLite `backend/data/accounts.db`), нууц үгийн хэш, session cookie |
| `auth.py` | Cookie нэр, буруу оролдлогын хязгаар |
| `test_system.py` | Тест |

## Хамгаалалт

- Нууц үг: PBKDF2-SHA256, 200,000 давталт, хэрэглэгч бүрт тусдаа salt. Байхгүй хэрэглэгчийн хариу ч ижил удаан.
- Session: HMAC гарын үсэгтэй cookie (`httpOnly`, `SameSite=Lax`, HTTPS дээр `Secure`). Нууц үг солиход хуучин нэвтрэлтүүд хүчингүй.
- Буруу оролдлого: нэг IP **эсвэл** нэг и-мэйл рүү 10 минутад 5 удаа → түр хаана (429), оролдлого бүр 1с удаашрна.
- `backend/data/` (хэрэглэгчид, нууц түлхүүр) git-д орохгүй.

## Тест

```bash
.venv/bin/python backend/test_system.py     # -> ТЭНЦЛЭЭ ✓
```

Түр хавтсанд ажиллана — жинхэнэ хэрэглэгчдэд хүрэхгүй.
