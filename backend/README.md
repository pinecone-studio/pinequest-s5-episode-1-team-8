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

Жишээ дуудлага үүсгэх (вэбийг турших): `.venv/bin/python backend/demo_data.py`

Порт 8100 (SIM-TRUNK-ийн вэб 8000 дээр ажилладаг тул давхцахгүй). Солих: `API_PORT=...`

## API

| Хүсэлт | Юу хийх вэ |
|---|---|
| `POST /api/signup` `{"company", "phone", "email", "password"}` | Шинэ байгууллага + эзэмшигч хэрэглэгч үүсгээд нэвтэрнэ (нэг IP-ээс цагт 3) |
| `POST /api/login` `{"email", "password"}` | Зөв бол хэрэглэгч + httpOnly session cookie (`pc_session`, 7 хоног) |
| `POST /api/logout` | Cookie устгана |
| `GET /api/me` | Нэвтэрсэн хэрэглэгч, байгууллага `{email, role, tenant, tenant_name, extension, plan, expires}`, үгүй бол 401 |

| `GET /api/org` | Байгууллагын мэдээлэл, хэрэглэгчид, мэдээллийн файлын тоо |
| `PUT /api/org` `{"name", "phone", "email", "address", "hours"}` | Хадгална; мэндчилгээ, утас/хаяг/цагийн FAQ дахин үүснэ |
| `POST /api/account/password` `{"current", "new"}` | Нууц үг солих; энэ төхөөрөмж нэвтэрсэн хэвээр, бусад нь гарна |
| `GET /api/settings` | Telegram тохиргоо (токеныг өөрийг нь буцаахгүй) |
| `PUT /api/settings/telegram` `{"token"}` / `{"chat_id", "chat_title"}` | Ботын токен / мэдэгдэл очих групп |
| `GET /api/settings/telegram/chats` | Ботод мессеж бичсэн группууд |
| `POST /api/settings/telegram/test` | Тест мессеж |
| `GET /api/calls?limit=100&q=&unanswered=&days=` | Сүүлийн дуудлагууд (асуултын тоо, хариулж чадаагүй тоо); дугаар/ярианы үгээр хайх, зөвхөн хариулж чадаагүй, сүүлийн N хоног |
| `GET /api/calls/{uuid}` | Нэг дуудлагын бүх яриа |
| `GET /api/stats` | Самбар: дуудлага, хариулсан/чадаагүй, хариултын зам, шинэ бүртгэл, сүүлийн 5 өдөр |
| `GET /api/leads` | Бүртгэл: бүртгүүлэх / ажилтантай ярих хүсэлтүүд |
| `PATCH /api/leads/{id}` `{"status"?, "notes"?}` | Төлөв (`new`, `contacted`, `done`), тэмдэглэл |
| `GET /api/unanswered?limit=200` | AI хариулж чадаагүй асуултууд (дахин асуусан, тодруулсан, ажилтанд шилжүүлсэн) |
| `GET /api/unanswered/review` | Асуултыг ажиллаж буй SIM-TRUNK AI-аар дахин шалгаж, шийдэгдсэн/чимээ/шийдэх ангилал болон ойр хариултын санал авна |
| `POST /api/unanswered/hide` `{"q"}` | Шийдэгдсэн эсвэл чимээ асуултыг ажлын жагсаалтаас нууна (дуудлагын лог хэвээр) |
| `POST /api/unanswered/teach` `{"q", "answer"}` | Байгаа FAQ/мэдээллийг зөв хариулт болгон заана |
| `POST /api/unanswered/answer` `{"q", "answer", "questions"}` | Байгууллагын бичсэн баталгаатай шинэ хариултыг давхардалгүй FAQ болгоно |
| `POST /api/unanswered/apply` | Шинэ хариултын аудио үүсгэж selector сургалтыг дараалалд оруулна |
| `GET /api/status` | AI сервер / SIP асаалттай эсэх, мэдээлэл бэлэн эсэх, бэлдэлт, sidebar-ын тоо (вэб 10с тутам асууна) |
| `GET /api/admin/tenants` | (admin) Бүх байгууллага: хэрэглэгч, дуудлага, эрх, бэлэн эсэх |
| `POST /api/admin/tenants` `{"name", "phone", "email", "address", "hours", "owner_email", "password"}` | (admin) Шинэ байгууллага + эзэмшигч хэрэглэгч |
| `POST /api/admin/switch` `{"slug"}` | (admin) Өөр байгууллагыг сольж харах |
| `DELETE /api/admin/switch` | (admin) Өөрийн байгууллага руу буцах |
| `POST /api/admin/plan` `{"slug", "plan"}` | (admin) Эрх: `trial`, `active`, `suspended` |
| `GET /api/admin/eleven` | (admin) ElevenLabs: түлхүүртэй эсэх, хоолойнууд (монгол эхэнд), өгүүлбэр бүрийн жишээ |
| `POST /api/admin/eleven/key` `{"key"}` | (admin) ElevenLabs түлхүүр шалгаад `data/elevenlabs_key`-д (600) |
| `POST /api/admin/eleven/generate` `{"voice", "scope"}` | (admin) Жишээ аудио үүсгэх: `sample` (8) эсвэл `all` |
| `PUT /api/admin/eleven/choice` `{"voice"}` | (admin) Байгууллагын хоолой (анхдагч Уянга) |
| `GET /api/admin/eleven/audio/{voice}/{hash}` | (admin) Жишээ аудио (`?phone=1` утасны чанар) |
| `POST /api/voice/recording/{hash}` file=WAV | Өгүүлбэрийг өөрийн хоолойгоор (24kHz mono болгоно) — "Бэлдэх"-д ElevenLabs-ийн оронд |
| `DELETE /api/voice/recording/{hash}` | Бичлэг устгах (ElevenLabs руу буцна) |
| `GET /api/voice/audio/{hash}` | Одоо тоглогдох аудио: бичлэг эсвэл ElevenLabs (`?phone=1` утасны чанар) |
| `POST /api/voice/rebuild` | Хоолой (ElevenLabs), толь, бичлэгийн дагуу аудиог шинэчлэх (сургалтгүй) |
| `GET /api/voice/export` | Одоо тоглогдох бүх аудио + manifest (json, csv) -> ZIP |

Бусад бүх `/api/*` нэвтрэлт шаардана (middleware). `/docs` хаалттай.
Хүсэлт бүрт хэрэглэгчийн байгууллага `request.state.tenant`-д тогтоно — route-ууд `Depends(current_tenant)`-ээр авч зөвхөн тэр байгууллагын өгөгдлийг хэрэглэнэ.

## Файлууд

| Файл | Үүрэг |
|---|---|
| `app.py` | FastAPI: бүртгүүлэх, нэвтрэх, гарах, `/api/me`, нэвтрэлт шалгах middleware |
| `tenant.py` | Байгууллага: `backend/data/tenants/<slug>/` (config.json, faq.json, knowledge/), загвар FAQ |
| `speech.py` | Тоо, утасны дугаарыг монгол үгээр (FAQ-ийн хариултад) |
| `routes/org.py` | Байгууллагын мэдээлэл (Тохируулах) |
| `routes/account.py` | Нууц үг солих |
| `routes/settings.py`, `notify.py` | Telegram мэдэгдэл (байгууллага бүрийн `data/settings.json`, 0600) |
| `routes/calls.py`, `db.py` | Яриа: дуудлагын лог (байгууллага бүрийн `data/receptionist.db`) |
| `routes/stats.py` | Самбарын статистик |
| `routes/leads.py` | Бүртгэл (lead) |
| `routes/unanswered.py` | Хариулж чадаагүй асуултууд |
| `routes/status.py` | AI ресепшний төлөв |
| `routes/admin.py` | Платформын admin: байгууллагууд, эрх, сольж харах |
| `routes/eleven.py`, `eleven.py` | ElevenLabs хоолой (Oron-гүй): түлхүүр, хоолой сонгох, жишээ аудио (`eleven_samples.py` SIM-TRUNK-ийн орчинд) |
| `routes/voice.py`, `audio_files.py` | Хоолой: өгүүлбэрүүд, толь, өөрийн бичлэг (`tenants/<slug>/recordings/<hash>.wav`, SIM-TRUNK-тэй ижил) |
| `demo_data.py` | Жишээ дуудлага, бүртгэл үүсгэх (утасны AI бэлэн болохоос өмнө вэбийг турших) |
| `sim_runner.py` | SIM-TRUNK-ийн скриптийг (ingest, TTS ...) манай байгууллагын хавтсаар ажиллуулна — "Аудио бэлдэх" |
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
