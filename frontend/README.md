# Frontend (Next.js + React + Tailwind)

AI ресепшний вэб удирдлага. Next.js 16 (App Router), React 19, Tailwind CSS 4, багц менежер **bun**.

## Ажиллуулах

Эхлээд backend-ийг асаана (`backend/README.md`), дараа нь:

```bash
cd frontend
bun install
bun dev              # http://localhost:3000
```

`/api/*` хүсэлтүүд backend руу дамжина (`next.config.ts` → `API_URL`, анхдагч `http://127.0.0.1:8100`).

```bash
bun run lint
bun run build
```

## Бүтэц

```
app/
  layout.tsx                 html, фонт, өнгө
  globals.css                Tailwind + өнгөний токенууд (bg-panel, text-muted, border-line, bg-brand ...)
  login/page.tsx             Нэвтрэх хуудас
  signup/page.tsx            Байгууллага бүртгүүлэх
  (dashboard)/layout.tsx     Нэвтэрсний дараах хүрээ: sidebar + хуудас
  (dashboard)/page.tsx       Самбар
  (dashboard)/setup/         Тохируулах (байгууллагын мэдээлэл, алхмууд)
  (dashboard)/settings/      Тохиргоо (Telegram мэдэгдэл, нууц үг)
  (dashboard)/calls/         Яриа: дуудлагын жагсаалт, calls/[uuid] — нэг дуудлагын яриа
  (dashboard)/[section]/     Хараахан хийгдээгүй хэсгүүдийн түр хуудас
  error.tsx                  Backend унтарсан үед
components/
  auth/                      AuthCard, LoginForm, SignupForm
  sidebar/                   Sidebar, NavLinks, UserCard, LogoutButton
  setup/                     Step, OrgForm
  settings/                  TelegramSettings, PasswordForm
  calls/                     CallsTable, ChatMessage, RouteTag
  ui/                        Button, Field, Card, Tag, Alert
  Brand.tsx, PageHeader.tsx, Section.tsx
lib/
  session.ts                 getUser() / requireUser() — cookie-г backend (/api/me) шалгана
  api.ts                     apiGet() — server component-оос backend-ийн өгөгдөл унших
  client.ts                  apiSend() — client component-оос backend руу (алдааны мессежтэй)
  useAction.ts               Хадгалах/устгах үйлдэл: pending, алдаа, амжилт, дараа нь хуудсыг шинэчилнэ
  nav.tsx                    Sidebar-ын цэс
  config.ts, types.ts, format.ts
proxy.ts                     Cookie огт байхгүй бол хуудсыг зурахгүй, шууд /login руу
```

## Шинэ хэсэг нэмэх

Жишээ нь "Яриа": `app/(dashboard)/calls/page.tsx` үүсгээд эхэнд нь `await requireUser()` дуудна.
Өгөгдлийг server талд `apiGet()`-ээр уншиж, өөрчлөхдөө client component-д `useAction()` + `apiSend()`.
Цэс `lib/nav.tsx`-д аль хэдийн бий. Жишээ дуудлага: `.venv/bin/python backend/demo_data.py`. Фонт локал (`app/fonts/`) — Google Fonts руу хандахгүй.
