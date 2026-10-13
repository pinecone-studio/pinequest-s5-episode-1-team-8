# Frontend-ийн дараагийн 4 PR ажил

Эдгээр ажил `origin/main` дээр хараахан хийгдээгүй. Бүгд жижиг frontend ажил бөгөөд backend endpoint, API response, JSON файл өөрчлөхгүй.

PR бүр хоорондоо хамааралгүй. Нэг ажлыг эхлэх бүрдээ `main`-ээс шинэ branch үүсгэнэ:

```bash
git switch main
git pull --ff-only origin main
git switch -c <branch-name>
```

Нэг PR-д зөвхөн тухайн ажилд заасан файлуудыг оруулна. Шинэ package суулгахгүй.

## PR 1 — Нууц үгээ давтаж бичдэг шалгалт

- **Өөрчлөх файлууд:**
  - `frontend/components/auth/SignupForm.tsx`
  - `frontend/components/settings/PasswordForm.tsx`
- **Branch:** `frontend/password-confirmation`
- **PR title:** `fix(frontend): validate password confirmation`

### Зорилго

Хэрэглэгч нууц үгээ андуурч бичээд бүртгүүлэх эсвэл солихоос сэргийлнэ.

### Хийх зүйл

- Бүртгүүлэх form-д `Нууц үгээ давтах` password field нэмнэ.
- Нууц үг солих form-д `Шинэ нууц үгээ давтах` password field нэмнэ.
- Submit хийхэд хоёр шинэ нууц үг ижил биш бол API дуудахгүй.
- Ижил биш үед form-ийн доор `Нууц үг таарахгүй байна` гэсэн ойлгомжтой алдаа харуулна.
- Алдаа гарсны дараа хэрэглэгч утгаа засаж дахин submit хийж чаддаг байна.
- Confirmation утгыг backend руу явуулахгүй. Одоогийн API payload-ийн field-үүдийг өөрчлөхгүй.
- Одоогийн required, `minLength={8}`, loading болон server error төлөвийг хэвээр үлдээнэ.

### Шалгах зүйл

- Хоёр нууц үг өөр үед request явахгүй, алдаа харагдана.
- Хоёр нууц үг ижил үед бүртгэл болон нууц үг солих request хэвийн явна.
- `Харуулах/Нуух` товч бүх password field дээр хэвийн ажиллана.
- Submit pending үед давхар request явуулахгүй.
- `bun run lint` болон `bun run build` амжилттай ажиллана.

---

## PR 2 — FAQ жагсаалт дотроо хайх ба TODO шүүх

- **Үндсэн файл:** `frontend/components/faq/FaqEditor.tsx`
- **Branch:** `frontend/faq-search-filter`
- **PR title:** `feat(frontend): add FAQ search and TODO filter`

### Зорилго

FAQ олон болсон үед хэрэгтэй асуулт, хариултаа хурдан олоход тусална.

### Хийх зүйл

- `Нийт ... FAQ` гарчгийн доор search input нэмнэ.
- Хайлт нь FAQ-ийн `id`, асуултууд болон хариултын текстээс хайдаг байна.
- Том/жижиг үсэг ялгахгүй, эхлэл/төгсгөлийн хоосон зайг үл тооцно.
- `Зөвхөн TODO` checkbox нэмнэ. Идэвхтэй үед хариултдаа `TODO` агуулсан FAQ-г л харуулна.
- Search болон checkbox хоёрыг зэрэг хэрэглэж болдог байна.
- `Харагдаж буй X / Нийт Y` гэсэн тоо харуулна.
- Шүүлтүүрт тохирох зүйл байхгүй үед `Тохирох FAQ олдсонгүй` гэсэн empty state гаргана.
- Шүүлтүүр нь зөвхөн харагдацыг өөрчилнө. FAQ устгах, нэмэх, засах, хадгалах ажиллагааг өөрчлөхгүй.
- Search хийсэн үед устгах товч зөв FAQ-г устгадаг байх ёстой. Array-ийн харагдаж буй index-ийг анхны index гэж андуурч болохгүй.

### Шалгах зүйл

- `id`, асуулт, хариултын аль ч үгээр зөв хайна.
- Монгол болон англи том/жижиг үсгийн хайлт ажиллана.
- `Зөвхөн TODO` болон search хамт зөв ажиллана.
- Шүүсэн жагсаалтаас засварлах, устгах үед зөв FAQ өөрчлөгдөнө.
- Search-ээ цэвэрлэхэд бүх FAQ буцаж харагдана.
- `bun run lint` болон `bun run build` амжилттай ажиллана.

---

## PR 3 — Дуудлагын яриаг нэг товчоор хуулах

- **Шинэ файл:** `frontend/components/calls/CopyTranscriptButton.tsx`
- **Өөрчлөх файл:** `frontend/app/(dashboard)/calls/[uuid]/page.tsx`
- **Branch:** `frontend/call-transcript-copy`
- **PR title:** `feat(frontend): add call transcript copy button`

### Зорилго

Байгууллагын ажилтан дуудлагын яриаг тайлан, чат эсвэл тэмдэглэл рүү амархан хуулдаг болгоно.

### Хийх зүйл

- Дуудлагын detail хуудасны header action хэсэгт `Яриаг хуулах` товч нэмнэ.
- Товчийг шинэ client component дотор хийнэ. Detail page өөрөө server component хэвээр үлдэнэ.
- Хуулах текстийн эхэнд дуудлагын огноо, залгагчийн дугаар, үргэлжилсэн хугацаа байна.
- Дараа нь message бүрийг шинэ мөрөнд дараах хэлбэрээр оруулна:
  - `Залгагч: ...`
  - `AI: ...`
- `navigator.clipboard.writeText` ашиглана.
- Амжилттай хуулсны дараа товчны текст 2 секунд орчим `Хууллаа ✓` болно.
- Clipboard ажиллахгүй үед `Хуулж чадсангүй` гэсэн feedback харуулна; хуудас эвдрэхгүй.
- Message байхгүй үед товч disabled байна.
- Одоогийн `← Бүх яриа` холбоосыг хэвээр үлдээнэ.

### Шалгах зүйл

- Message-тэй дуудлага дээр товч бүх яриаг зөв дарааллаар хуулна.
- Залгагч болон AI мөрүүд ялгаатай, уншихад ойлгомжтой байна.
- Дугаар тодорхойгүй үед `дугаар тодорхойгүй` гэж орно.
- Message байхгүй үед товч disabled байна.
- Амжилт болон алдааны feedback screen reader-д мэдэгдэх `aria-live`-тай байна.
- `bun run lint` болон `bun run build` амжилттай ажиллана.

---

## PR 4 — “Хэрэгжүүлэх” үйлдэлд нэгдсэн confirm dialog ашиглах

- **Өөрчлөх файл:** `frontend/components/unanswered/UnansweredManager.tsx`
- **Ашиглах component:** `frontend/components/ui/ConfirmDialog.tsx`
- **Branch:** `frontend/unanswered-apply-dialog`
- **PR title:** `fix(frontend): confirm unanswered changes with dialog`

### Зорилго

Хариулаагүй асуултын өөрчлөлтийг хэрэгжүүлэх үед browser-ийн `window.confirm` биш, web-ийн бусад хэсэгтэй ижил dialog харуулна.

### Хийх зүйл

- `window.confirm` ашигласан хэсгийг устгана.
- `Хэрэгжүүлэх · аудио + сургалт` товч дарахад `ConfirmDialog` нээгддэг болгоно.
- Dialog-ийн утга:
  - Гарчиг: `Өөрчлөлтийг хэрэгжүүлэх үү?`
  - Тайлбар: шинэ хариултын аудио үүсэж, AI сургалт ажиллахыг ойлгомжтой хэлнэ.
  - Confirm label: `Хэрэгжүүлэх`
  - Cancel label: `Цуцлах`
  - Danger өнгө ашиглахгүй.
- Confirm дарсны дараа одоогийн `/api/unanswered/apply` request яг нэг удаа явна.
- Request ажиллаж байх үед dialog болон үндсэн товчны pending/disabled төлөв зөв байна.
- Амжилттай бол dialog хаагдаж, одоогийн success message харагдана.
- API алдаа гарвал dialog хаагдаж, одоогийн error message харагдана. Хэрэглэгч дахин оролдож чадна.
- Cancel болон `Escape` үед request огт явахгүй.

### Шалгах зүйл

- Pending өөрчлөлт байхад үндсэн товч dialog нээнэ.
- Cancel болон `Escape` ямар ч action хийхгүй.
- Confirm хийхэд request нэг удаа явна.
- Давхар товшилтоор хоёр request явуулахгүй.
- Амжилт/алдааны дараа хуудас хэвийн ашиглагдана.
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

> Анхаарах: backend файл, API contract, JSON өгөгдөл өөрчлөхгүй. Шинэ dependency суулгахгүй. Даалгаварт бичээгүй нэмэлт refactor хийхгүй.
