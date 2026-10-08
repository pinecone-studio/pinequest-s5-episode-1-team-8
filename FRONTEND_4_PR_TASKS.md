# Frontend-ийн 4 жижиг PR ажил

Эдгээр ажлыг тус тусад нь PR болгоно. Зөвхөн `frontend/` дотор ажиллаж, backend, API болон JSON өгөгдөлд өөрчлөлт оруулахгүй.

## PR 1 — Mobile цэсийг `Escape`-аар хаах

- **Файл:** `frontend/components/sidebar/MobileMenu.tsx`
- **Branch:** `frontend/mobile-menu-escape`
- **PR title:** `feat(frontend): close mobile menu with Escape`

### Хийх зүйл

- `useEffect` ашиглан цэс нээлттэй үед `document`-ийн `keydown` event сонсоно.
- `Escape` дарахад `setOpen(false)` дуудна.
- Цэс хаалттай үед listener нэмэхгүй, cleanup дээр listener-ээ салгана.
- Одоогийн товч болон холбоосоор хаах ажиллагааг хэвээр үлдээнэ.

### Шалгах

- Mobile цэс нээлттэй үед `Escape` дарахад хаагдана.
- Цэсний холбоос дарахад өмнөх шигээ хаагдана.
- `bun run lint` амжилттай ажиллана.

---

## PR 2 — Logout товчны loading төлөв

- **Файл:** `frontend/components/sidebar/LogoutButton.tsx`
- **Branch:** `frontend/logout-loading-label`
- **PR title:** `feat(frontend): improve logout loading feedback`

### Хийх зүйл

- `pending` үед `title` болон `aria-label`-ийг `Гарч байна…` болгоно. Энгийн үед `Гарах` байна.
- `pending` үед logout icon-ы оронд `animate-spin` class-тай жижиг spinner харуулна.
- Одоогийн `disabled={pending}` болон logout logic-ийг өөрчлөхгүй.

### Шалгах

- Дарахаас өмнө `Гарах`, дарсны дараа `Гарч байна…` гэж уншигдана.
- Хүлээж байх үед spinner харагдаж, дахин дарагдахгүй.
- Logout хийгдээд `/login` руу шилжинэ.
- `bun run lint` амжилттай ажиллана.

---

## PR 3 — Идэвхтэй calls filter-ийн тоо

- **Файл:** `frontend/components/calls/CallsFilter.tsx`
- **Branch:** `frontend/calls-active-filter-count`
- **PR title:** `feat(frontend): show active calls filter count`

### Хийх зүйл

- `q`, `days`, `unanswered` утгуудаас хэд нь идэвхтэйг `activeCount`-оор тоолно.
- `activeCount > 0` үед `Цэвэрлэх` холбоосын өмнө `1 шүүлтүүр идэвхтэй` гэх текст харуулна.
- Тоо нь сонгосон шүүлтүүрээс автоматаар шинэчлэгдэнэ.
- Одоогийн URL query болон цэвэрлэх ажиллагааг өөрчлөхгүй.

### Шалгах

- Шүүлтүүргүй үед тоо болон `Цэвэрлэх` харагдахгүй.
- 1–3 шүүлтүүр сонгоход зөв тоо харагдана.
- `Цэвэрлэх` дарахад бүх шүүлтүүр болон тоо арилна.
- `bun run lint` амжилттай ажиллана.

---

## PR 4 — Setup banner-ийн mobile байрлал

- **Файл:** `frontend/components/dashboard/SetupBanner.tsx`
- **Branch:** `frontend/setup-banner-mobile`
- **PR title:** `fix(frontend): improve setup banner on mobile`

### Хийх зүйл

- Banner-ийн wrapper-ийг mobile үед босоо, `sm`-ээс дээш хөндлөн байрлалтай болгоно (`flex-col sm:flex-row`).
- `Тохируулах →` холбоосыг mobile үед бүтэн өргөн, голлуулсан болгоно (`w-full text-center sm:w-auto`).
- Текст, route, өнгө болон component logic-ийг өөрчлөхгүй.

### Шалгах

- Mobile дээр товч тайлбарын доор бүтэн өргөн харагдана.
- Том дэлгэц дээр тайлбар зүүн, товч баруун талд байна.
- Товч `/setup` руу зөв шилжинэ.
- `bun run lint` амжилттай ажиллана.

---

## PR description

```markdown
## Юу хийсэн
- ...

## Яаж шалгасан
- [ ] `bun run lint`
- [ ] Browser дээр гараар шалгасан

## Screenshot
<!-- Өөрчлөлт харагдах screenshot оруулна. -->
```

> Анхаарах: Нэг PR-д зөвхөн тухайн ажлын файлыг өөрчилж, бусад өөрчлөлтийг хамт оруулахгүй.
