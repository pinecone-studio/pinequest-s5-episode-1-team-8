<!--
⚠️ PR нээхийн өмнө:
  1. Дээрх "base:" нь **main** эсэхийг шалга (өөр feat/... branch биш). Эс бөгөөс merge хийхэд main-д орохгүй.
  2. Label сонго: backend / frontend
  3. Merge хийсний дараа "Delete branch" дарна.
-->

## Юу өөрчилсөн
-

## Шалгах
```bash
.venv/bin/python backend/test_system.py   # backend өөрчилсөн бол
cd frontend && bun run lint && bun run build   # frontend өөрчилсөн бол
```
