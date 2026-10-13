# Frontend-ийн дараагийн 5 PR ажил

Эдгээр ажлыг 2026-10-13-ны хамгийн сүүлийн `origin/main` болон GitHub-ийн бүх open/merged PR-тэй тулгаж шалгасан. Одоогоор хийгдээгүй, backend мэдэх шаардлагагүй frontend ажлууд.

PR бүр хоорондоо хамааралгүй. Нэг ажлыг эхлэх бүрдээ `main`-ээс шинэ branch үүсгэнэ:

```bash
git switch main
git pull --ff-only origin main
git switch -c <branch-name>
```

Нэг PR-д зөвхөн тухайн ажилд заасан файлуудыг оруулна. Backend, API contract, JSON өгөгдөл өөрчлөхгүй. Шинэ package суулгахгүй.

## PR 1 — Нууц үгээ давтаж шалгах

- **Өөрчлөх файлууд:**
  - `frontend/components/auth/SignupForm.tsx`
  - `frontend/components/settings/PasswordForm.tsx`
- **Branch:** `frontend/password-confirmation`
- **PR title:** `fix(frontend): validate password confirmation`

### Зорилго

Бүртгүүлэх болон нууц үг солих үед хэрэглэгч шинэ нууц үгээ алдаатай бичихээс сэргийлнэ.

### Хийх зүйл

- Signup form-д `Нууц үгээ давтах` password field нэмнэ.
- Password form-д `Шинэ нууц үгээ давтах` password field нэмнэ.
- Submit хийхэд хоёр шинэ нууц үг ижил биш бол API дуудахгүй.
- `Нууц үг таарахгүй байна` гэсэн ойлгомжтой алдаа харуулна.
- Алдаа гарсны дараа хэрэглэгч утгаа засаад дахин submit хийж чадна.
- Давтан бичсэн утгыг backend руу явуулахгүй. Одоогийн API payload-ийг хэвээр үлдээнэ.
- Одоогийн required, `minLength={8}`, loading болон server error төлөвийг эвдэхгүй.

### Шалгах зүйл

- Хоёр нууц үг өөр үед request явахгүй.
- Ижил үед бүртгэл болон нууц үг солих request хэвийн явна.
- Бүх password field-ийн `Харуулах/Нуух` товч ажиллана.
- Pending үед давхар request явуулахгүй.
- `bun run lint` болон `bun run build` амжилттай ажиллана.

---

## PR 2 — FAQ хайлт болон TODO шүүлтүүр

- **Үндсэн файл:** `frontend/components/faq/FaqEditor.tsx`
- **Branch:** `frontend/faq-search-filter`
- **PR title:** `feat(frontend): add FAQ search and TODO filter`

### Зорилго

FAQ олон болсон үед хэрэгтэй асуулт, хариултаа хурдан олох боломжтой болгоно.

### Хийх зүйл

- `Нийт ... FAQ` хэсгийн доор search input нэмнэ.
- FAQ-ийн `id`, асуултууд болон хариултаас хайдаг байна.
- Том/жижиг үсэг ялгахгүй, хайлтын хоёр талын хоосон зайг үл тооцно.
- `Зөвхөн TODO` checkbox нэмнэ.
- Search болон TODO шүүлтүүрийг зэрэг ашиглаж болдог байна.
- `Харагдаж буй X / Нийт Y` гэсэн тоо харуулна.
- Тохирох зүйл байхгүй үед `Тохирох FAQ олдсонгүй` гэж харуулна.
- Шүүлтүүр нь зөвхөн харагдацыг өөрчилнө. FAQ нэмэх, хувилах, засах, устгах, хадгалах ажиллагааг өөрчлөхгүй.
- Шүүсэн жагсаалтаас засах, хувилах, устгах үед зөв FAQ дээр action ажиллана. Харагдаж буй index-ийг анхны index гэж андуурч болохгүй.

### Шалгах зүйл

- ID, асуулт, хариултын аль ч үгээр хайна.
- Монгол болон англи том/жижиг үсгийн хайлт ажиллана.
- TODO checkbox болон search хамт зөв ажиллана.
- Шүүлтүүртэй үед хувилах/устгах action зөв FAQ дээр ажиллана.
- Search-ээ цэвэрлэхэд бүх FAQ буцаж харагдана.
- `bun run lint` болон `bun run build` амжилттай ажиллана.

---

## PR 3 — Хариулаагүй асуултын “Хэрэгжүүлэх” dialog

- **Өөрчлөх файл:** `frontend/components/unanswered/UnansweredManager.tsx`
- **Ашиглах component:** `frontend/components/ui/ConfirmDialog.tsx`
- **Branch:** `frontend/unanswered-apply-dialog`
- **PR title:** `fix(frontend): confirm unanswered changes with dialog`

### Зорилго

`Хэрэгжүүлэх · аудио + сургалт` үйлдэлд browser-ийн `window.confirm` биш, web-ийн нэгдсэн dialog ашиглана.

### Хийх зүйл

- Одоогийн `window.confirm`-ийг устгана.
- Үндсэн товч дарахад `ConfirmDialog` нээгддэг болгоно.
- Dialog-ийн утга:
  - Гарчиг: `Өөрчлөлтийг хэрэгжүүлэх үү?`
  - Тайлбар: шинэ хариултын аудио үүсэж, AI сургалт ажиллахыг ойлгомжтой хэлнэ.
  - Confirm label: `Хэрэгжүүлэх`
  - Cancel label: `Цуцлах`
  - Danger өнгө ашиглахгүй.
- Confirm дарахад одоогийн `/api/unanswered/apply` request яг нэг удаа явна.
- Request ажиллах үед dialog болон үндсэн товч pending/disabled байна.
- Амжилт болон алдааны дараа dialog хаагдаж, одоогийн feedback харагдана.
- Cancel болон `Escape` үед request явахгүй.

### Шалгах зүйл

- Pending өөрчлөлт байхад товч dialog нээнэ.
- Cancel болон Escape ямар ч action хийхгүй.
- Confirm хийхэд request нэг удаа явна.
- Давхар товшилтоор хоёр request явуулахгүй.
- Алдааны дараа дахин оролдож болно.
- `bun run lint` болон `bun run build` амжилттай ажиллана.

---

## PR 4 — Сануулгын мессежийн тэмдэгтийн тоолуур

- **Үндсэн файл:** `frontend/components/settings/ReminderTemplate.tsx`
- **Branch:** `frontend/reminder-character-counter`
- **PR title:** `feat(frontend): show reminder message character count`

### Зорилго

AI сануулгын мессеж хэт урт болохоос өмнө хэрэглэгчид уртыг нь ойлгомжтой харуулна.

### Хийх зүйл

- Textarea-ийн доор `Одоогийн урт / 600 тэмдэгт` гэсэн live counter нэмнэ.
- 540 тэмдэгтээс бага үед counter muted өнгөтэй байна.
- 540–599 үед warning өнгө болон `Хязгаарт ойртлоо` тайлбар харуулна.
- 600 хүрэхэд `Дээд хязгаарт хүрлээ` гэж харуулна.
- Counter-д `aria-live="polite"` хэрэглэнэ.
- Зөвхөн хоосон зайтай мессежийг хадгалах товч disabled байна.
- Pending үед одоогийн хоёр товч disabled хэвээр байна.
- `Анхдагч руу`, preview болон хадгалах API ажиллагааг өөрчлөхгүй.

### Шалгах зүйл

- Бичих бүрд counter шууд шинэчлэгдэнэ.
- 539, 540, 600 тэмдэгтийн өнгө/тайлбар зөв солигдоно.
- 600-аас илүү бичигдэхгүй.
- Хоосон эсвэл зөвхөн зайтай үед хадгалах боломжгүй.
- Анхдагч мессеж рүү буцаах хэвийн ажиллана.
- `bun run lint` болон `bun run build` амжилттай ажиллана.

---

## PR 5 — Admin байгууллагын хайлт ба төлөвийн шүүлтүүр

- **Шинэ файл:** `frontend/components/admin/TenantList.tsx`
- **Өөрчлөх файл:** `frontend/app/(dashboard)/admin/page.tsx`
- **Дахин ашиглах component:** `frontend/components/admin/TenantRow.tsx`
- **Branch:** `frontend/admin-tenant-filter`
- **PR title:** `feat(frontend): add admin tenant search and filters`

### Зорилго

Байгууллага олон болсон үед admin хэрэгтэй байгууллагаа хурдан олдог болгоно.

### Хийх зүйл

- `TenantList` client component үүсгээд байгууллагын хүснэгт болон шүүлтүүрийг түүнд байрлуулна.
- Admin page server component хэвээр үлдэж, API-аас авсан `tenants`-ийг `TenantList`-д дамжуулна.
- Нэр, slug, байгууллагын и-мэйл болон хэрэглэгчийн и-мэйлээр хайдаг input нэмнэ.
- Том/жижиг үсэг ялгахгүй хайна.
- Төлөвийн select нэмнэ:
  - `Бүгд`
  - `Бэлэн`
  - `Бэлдээгүй`
  - `Ажил ажиллаж байгаа`
  - `Алдаатай`
- `Харагдаж буй X / Нийт Y` тоо болон `Цэвэрлэх` товч нэмнэ.
- Тохирох байгууллага байхгүй үед `Тохирох байгууллага олдсонгүй` empty state харуулна.
- `TenantRow`-ийн эрх солих, байгууллага руу орох ажиллагааг өөрчлөхгүй.
- Backend руу шинэ query эсвэл request нэмэхгүй; бүх шүүлтүүр browser дээр ажиллана.

### Шалгах зүйл

- Нэр, slug болон хоёр төрлийн и-мэйлээр зөв хайна.
- Search болон төлөвийн select хамт ажиллана.
- Цэвэрлэхэд бүх байгууллага буцаж харагдана.
- Шүүсэн мөрөөс эрх солих болон `Харах` товч хэвийн ажиллана.
- Байгууллага огт байхгүй үндсэн empty state хэвээр ажиллана.
- Mobile дээр controls багтаж, хүснэгтийн одоогийн scroll эвдрэхгүй.
- `bun run lint` болон `bun run build` амжилттай ажиллана.

---

## PR description загвар

```markdown
## Юу хийсэн
- ...

## Яаж шалгасан
- [ ] `bun run lint`
- [ ] `bun run build`
- [ ] Browser дээр desktop/mobile хэмжээгээр шалгасан
- [ ] Keyboard-аар шалгасан

## Screenshot / video
<!-- Өөрчлөлтийн desktop болон mobile харагдацыг оруулна. -->
```

> Open PR #151-ийн дуудлагын TXT татах ажлыг энэ жагсаалтад оруулаагүй. Даалгаварт бичээгүй нэмэлт refactor хийхгүй.
