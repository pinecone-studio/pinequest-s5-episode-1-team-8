# Frontend-ийн дараагийн 4 PR ажил

Доорх ажлууд `origin/main` дээр хараахан хийгдээгүй. PR бүр зөвхөн `frontend/` дотор хийгдэх бөгөөд backend endpoint, API response, JSON өгөгдөл өөрчлөхгүй.

PR-үүд хоорондоо хамааралгүй. Нэг PR-д зөвхөн тухайн ажлын файлуудыг оруулна.

## PR 1 — Calls жагсаалтад эрэмбэлэлт ба mobile card view

- **Үндсэн файл:** `frontend/components/calls/CallsTable.tsx`
- **Branch:** `frontend/calls-sort-mobile-view`
- **PR title:** `feat(frontend): improve calls list sorting and mobile view`

### Хийх зүйл

- Component-ийг client component болгоод `Хэзээ`, `Үргэлжилсэн`, `Хариулж чадаагүй` баганаар өсөх/буурах эрэмбэлэлт нэмнэ.
- Идэвхтэй баганын header дээр чиглэлийн тэмдэг (`↑`/`↓`) болон `aria-sort` харуулна.
- Анхны дараалал нь одоогийнхтой адил шинэ дуудлага эхэнд байна.
- Desktop дээр одоогийн table-ийг хадгална. Mobile (`md`-ээс доош) үед дуудлага бүрийг огноо, дугаар, хугацаа, асуултын тоо, unanswered badge бүхий card болгоно.
- Table болон card хоёул тухайн дуудлагын `/calls/[uuid]` хуудас руу ордог байна.
- Шинэ package суулгахгүй.

### Шалгах

- Гурван sortable header-ийг дарахад asc/desc зөв солигдоно.
- Эрэмбэлсний дараа зөв дуудлагын detail руу орно.
- 375px орчим өргөнд horizontal scroll үүсэхгүй, бүх мэдээлэл уншигдана.
- Keyboard-аар header болон row/card холбоосууд руу очиж ашиглаж болно.
- `bun run lint` болон `bun run build` амжилттай ажиллана.

---

## PR 2 — Database table-ийн багана сонголт ба cell copy

- **Үндсэн файл:** `frontend/components/database/DbTableView.tsx`
- **Branch:** `frontend/database-table-tools`
- **PR title:** `feat(frontend): add database table viewing tools`

### Хийх зүйл

- Component-ийг client component болгоно.
- `Багана` товч нээхэд checkbox жагсаалт харуулж, хэрэглэгч харагдах багануудаа сонгодог болгоно.
- Ядаж нэг багана заавал харагддаг байна; бүх баганыг нуухыг зөвшөөрөхгүй.
- Сонголтыг `localStorage`-д table-ийн нэрээр тусад нь хадгална.
- Cell дээр focus/hover хийхэд `Хуулах` товч гаргаж, текст утгыг clipboard-д хуулна.
- Амжилттай хуулсны дараа 1–2 секунд `Хууллаа` feedback харуулна. Clipboard ажиллахгүй үед эвдрэлгүй, ойлгомжтой алдаа үзүүлнэ.
- Pagination, search query болон vector/date formatting-ийн одоогийн ажиллагааг хэвээр үлдээнэ.

### Шалгах

- Багана нууж/харуулсны дараа refresh хийхэд сонголт хадгалагдана.
- Өөр table руу ороход тухайн table-ийн өөрийн сонголт ашиглагдана.
- Энгийн text/number/date cell зөв хуулагдана.
- Search болон `Өмнөх`/`Дараах` холбоосын query алдагдахгүй.
- Keyboard-аар багана сонгох болон хуулах боломжтой.
- `bun run lint` болон `bun run build` амжилттай ажиллана.

---

## PR 3 — Assistant chat-ийн input ба accessibility сайжруулалт

- **Үндсэн файл:** `frontend/components/assistant/AssistantChat.tsx`
- **Branch:** `frontend/assistant-chat-ux`
- **PR title:** `feat(frontend): improve assistant chat interactions`

### Хийх зүйл

- Нэг мөрийн `input`-ийг auto-resize хийдэг `textarea` болгоно; 1–5 мөр хүртэл өсдөг байна.
- `Enter` илгээж, `Shift+Enter` шинэ мөр оруулдаг болгоно.
- Илгээсний дараа focus-ийг textarea дээр хадгална.
- Message list-д `role="log"`, `aria-live="polite"`, `aria-relevant="additions"` тохируулж шинэ AI хариултыг screen reader уншдаг болгоно.
- Шинэ message нэмэгдэхэд доош auto-scroll хийнэ. Харин хэрэглэгч хуучин message уншихаар дээш scroll хийсэн үед хүчээр доош үсрүүлэхгүй; доор `Шинэ хариулт ↓` товч харуулна.
- Busy төлөвт input болон илгээх товч disabled байна, одоогийн example/keypad flow эвдэхгүй.

### Шалгах

- `Enter`, `Shift+Enter` хоёр тусдаа зөв ажиллана.
- Олон мөртэй текст textarea-г 5 мөр хүртэл өсгөнө.
- Доод хэсэгт байх үед шинэ message автоматаар харагдана.
- Дээш scroll хийсэн үед байрлал хадгалагдаж, `Шинэ хариулт ↓` товчоор доош очно.
- Caller/staff mode солих, шинэ яриа, example болон keypad хэвийн ажиллана.
- `bun run lint` болон `bun run build` амжилттай ажиллана.

---

## PR 4 — Нэгдсэн confirm dialog component

- **Шинэ файл:** `frontend/components/ui/ConfirmDialog.tsx`
- **Өөрчлөх файлууд:**
  - `frontend/components/faq/FaqEditor.tsx`
  - `frontend/components/voice/ClipList.tsx`
  - `frontend/components/training/TrainingManager.tsx`
- **Branch:** `frontend/reusable-confirm-dialog`
- **PR title:** `feat(frontend): add reusable confirmation dialog`

### Хийх зүйл

- Browser-ийн `window.confirm`-ийг орлох reusable dialog хийнэ.
- Props нь `open`, `title`, `description`, confirm/cancel callback, confirm label болон danger төлөвтэй байна.
- Dialog нээгдэхэд confirm биш, cancel товч эхэлж focus авна.
- `Escape`, backdrop болон `Цуцлах` товч dialog-ийг хаана; confirm callback дуудахгүй.
- Dialog хаагдсаны дараа focus өмнө дарсан товч руу буцна.
- FAQ устгах, voice recording устгах, ElevenLabs-аар дахин үүсгэх үйлдлүүдийг шинэ dialog-т холбоно.
- Training example устгах үйлдэлд мөн баталгаажуулалт нэмнэ.
- Pending үед товчнууд disabled болж, давхар action явуулахгүй.

### Шалгах

- Дөрвөн action бүр зөв гарчиг, тайлбартай dialog нээнэ.
- Cancel, backdrop, `Escape` үед ямар ч өгөгдөл өөрчлөгдөхгүй.
- Confirm хийхэд өмнөх API action яг нэг удаа ажиллана.
- Focus dialog дотроо зөв удирдагдаж, хаахад trigger товч руу буцна.
- Mobile болон desktop дээр dialog viewport-оос халихгүй.
- `bun run lint` болон `bun run build` амжилттай ажиллана.

---

## PR description

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

> Анхаарах: API contract өөрчлөх, backend файл засах, шинэ dependency суулгах шаардлагагүй. Scope томорвол тухайн PR-аас салгаж тусдаа issue болгоно.
