#!/usr/bin/env bash
# Backend (http://127.0.0.1:8100) + frontend (http://localhost:3000)-ийг зэрэг асаана.
# Ctrl+C дарахад хоёулаа унтарна.
#
#   ./dev.sh          # бүх код, өгөгдөл энэ repository дотроос ажиллана
set -u
cd "$(dirname "$0")"
if [ "${1:-}" = "--sim" ]; then
  echo "--sim сонголт хэрэггүй болсон. Зүгээр ./dev.sh ажиллуулна уу."
  exit 2
fi
# Хуучин shell session-д үлдсэн тохиргоо гаднын хавтас руу буцааж заахаас хамгаална.
unset SIM_TRUNK_LIVE SIM_TRUNK_DIR

if [ ! -x .venv/bin/python ]; then
  echo "Python орчин алга. Эхлээд нэг удаа:"
  echo "  uv venv --python 3.12 .venv && uv pip install --python .venv/bin/python -r backend/requirements.txt"
  exit 1
fi
# Багийн гишүүн шинэ сан нэмсэн бол автоматаар суулгана (өөрчлөлтгүй бол хэдхэн секунд)
if command -v uv >/dev/null 2>&1; then
  uv pip install -q --python .venv/bin/python -r backend/requirements.txt || exit 1
else
  .venv/bin/python -m pip install -q -r backend/requirements.txt || exit 1
fi
(cd frontend && bun install --silent) || exit 1
# Зөвхөн тухайн портыг СОНСОЖ буй серверийг шалгана (VS Code зэрэг холбогдсон програмыг биш)
for port in 8100 3000; do
  if lsof -ti "tcp:$port" -sTCP:LISTEN >/dev/null 2>&1; then
    echo "$port порт дээр өөр сервер ажиллаж байна. Өмнө асаасан ./dev.sh-ээ Ctrl+C-ээр унтраана уу,"
    echo "эсвэл: lsof -ti tcp:$port -sTCP:LISTEN | xargs kill"
    exit 1
  fi
done

# Ctrl+C эсвэл аль нэг нь унтарвал энэ скриптийн асаасан процессуудыг (хүүхдүүдтэй нь) унтраана.
# (kill 0 биш: скриптийг өөр програмаас дуудсан бол тэрийг нь хамт унтраах байсан)
killtree() { local child; for child in $(pgrep -P "$1"); do killtree "$child"; done; kill "$1" 2>/dev/null; }
cleanup() {
  trap - INT TERM EXIT
  for pid in ${api:-} ${web:-}; do killtree "$pid"; done
  wait 2>/dev/null
}
trap cleanup INT TERM EXIT

.venv/bin/python -u backend/app.py &
api=$!
(cd frontend && exec bun dev) &
web=$!

echo "Вэб: http://localhost:3000   (унтраах: Ctrl+C)"
# Аль нэг нь зогсвол (жишээ нь алдаа) нөгөөг нь ч унтраана. (macOS-ийн bash 3.2-т wait -n алга)
while kill -0 "$api" 2>/dev/null && kill -0 "$web" 2>/dev/null; do sleep 1; done
