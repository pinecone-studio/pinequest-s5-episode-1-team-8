# Backend (Python FastAPI)

AI ресепшний сервер тал. Вэб интерфейс нь `frontend/` (Next.js) — хөтөч backend руу шууд биш, Next.js-ээр дамжиж хандана.

## Суулгах, ажиллуулах

```bash
uv venv --python 3.12 .venv
uv pip install --python .venv/bin/python -r backend/requirements.txt

.venv/bin/python backend/app.py        # http://127.0.0.1:8100
```

Анх асахад жишиг байгууллага (Pinecone Academy) ба `admin` хэрэглэгч санамсаргүй нууц үгтэй үүсч, терминалд **нэг удаа** хэвлэгдэнэ.
Нууц үг солих: `.venv/bin/python backend/accounts.py admin admin`

Порт 8100 (SIM-TRUNK-ийн вэб 8000 дээр ажилладаг тул давхцахгүй). Солих: `API_PORT=...`

## API

| Хүсэлт | Юу хийх вэ |
|---|---|
| `POST /api/signup` `{"company", "phone", "email", "password"}` | Шинэ байгууллага + эзэмшигч хэрэглэгч үүсгээд нэвтэрнэ (нэг IP-ээс цагт 3) |
| `POST /api/login` `{"email", "password"}` | Зөв бол хэрэглэгч + httpOnly session cookie (`pc_session`, 7 хоног) |
| `POST /api/logout` | Cookie устгана |
| `GET /api/me` | Нэвтэрсэн хэрэглэгч, байгууллага `{email, role, tenant, tenant_name, extension, plan, expires}`, үгүй бол 401 |

Бусад бүх `/api/*` нэвтрэлт шаардана (middleware). `/docs` хаалттай.
Хүсэлт бүрт хэрэглэгчийн байгууллага `request.state.tenant`-д тогтоно — route-ууд `Depends(current_tenant)`-ээр авч зөвхөн тэр байгууллагын өгөгдлийг хэрэглэнэ.

## Файлууд

| Файл | Үүрэг |
|---|---|
| `app.py` | FastAPI: бүртгүүлэх, нэвтрэх, гарах, `/api/me`, нэвтрэлт шалгах middleware |
| `tenant.py` | Байгууллага: `backend/data/tenants/<slug>/` (config.json, faq.json, knowledge/), загвар FAQ |
| `speech.py` | Тоо, утасны дугаарыг монгол үгээр (FAQ-ийн хариултад) |
| `deps.py` | `current_user`, `current_tenant` |
| `config.py` | `DATA_DIR` (анхдагч `backend/data/`) |
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
