#!/usr/bin/env bash
# Backend (http://127.0.0.1:8100) + frontend (http://localhost:3000)-ийг зэрэг асаана.
# Ctrl+C дарахад хоёулаа унтарна.
#
#   ./dev.sh          # backend + frontend
#   ./dev.sh --ai     # install AI dependencies + web
#   ./dev.sh --phone  # web + AI dependencies + phone AI + SIP
set -u
cd "$(dirname "$0")"
mode="${1:-}"
WITH_AI=0
if [ "$mode" = "--ai" ] || [ "$mode" = "--phone" ]; then
  WITH_AI=1
fi
if [ "$mode" = "--sim" ]; then
  echo "--sim сонголт хэрэггүй болсон. Зүгээр ./dev.sh ажиллуулна уу."
  exit 2
fi
if [ -n "$mode" ] && [ "$mode" != "--phone" ] && [ "$mode" != "--ai" ]; then
  echo "Ашиглах: ./dev.sh [--ai|--phone]"
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
install() {   # $1 = requirements файл, $2 = "-q" (чимээгүй) эсвэл "" (явцыг харуулна)
  if command -v uv >/dev/null 2>&1; then
    uv pip install ${2:-} --python .venv/bin/python -r "$1"
  else
    .venv/bin/python -m pip install ${2:-} -r "$1"
  fi
}
echo "Сангуудыг шалгаж байна..."
install backend/requirements.txt -q || exit 1
if [ "$WITH_AI" = 1 ]; then
  echo "AI сангуудыг суулгаж байна (эхний удаа ~3GB татна, 5-15 минут — явц доор харагдана)..."
  install backend/requirements-ai.txt "" || exit 1
elif ! .venv/bin/python -c "import torch, sentence_transformers, mlx_whisper" >/dev/null 2>&1; then
  echo "ℹ️  AI сангууд суугаагүй: вэб ажиллана, харин «Аудио бэлдэх», AI сургалт, утасны AI-д хэрэгтэй."
  echo "   Суулгах: ./dev.sh --ai   (нэг удаа, ~3GB)"
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
if [ "$mode" = "--phone" ]; then
  if lsof -ti tcp:9092 -sTCP:LISTEN >/dev/null 2>&1; then
    echo "9092 порт дээр өөр AI сервер ажиллаж байна. Өмнөх процессыг унтраана уу."
    exit 1
  fi
  if lsof -ti udp:5060 >/dev/null 2>&1; then
    echo "5060 UDP порт дээр өөр SIP сервер ажиллаж байна. Өмнөх процессыг унтраана уу."
    exit 1
  fi
fi

# Ctrl+C эсвэл аль нэг нь унтарвал энэ скриптийн асаасан процессуудыг (хүүхдүүдтэй нь) унтраана.
# (kill 0 биш: скриптийг өөр програмаас дуудсан бол тэрийг нь хамт унтраах байсан)
killtree() { local child; for child in $(pgrep -P "$1"); do killtree "$child"; done; kill "$1" 2>/dev/null; }
cleanup() {
  trap - INT TERM EXIT
  for pid in ${api:-} ${web:-} ${ai:-} ${sip:-}; do killtree "$pid"; done
  wait 2>/dev/null
}
trap cleanup INT TERM EXIT

.venv/bin/python -u backend/app.py &
api=$!
(cd frontend && exec bun dev) &
web=$!
if [ "$mode" = "--phone" ]; then
  .venv/bin/python backend/run_ai.py phone &
  ai=$!
  .venv/bin/python backend/run_ai.py sip &
  sip=$!
fi

echo "Вэб: http://localhost:3000   (унтраах: Ctrl+C)"
if [ "$mode" = "--phone" ]; then
  echo "Утасны AI: AudioSocket 9092 + SIP 5060/UDP"
fi
# Аль нэг нь зогсвол (жишээ нь алдаа) нөгөөг нь ч унтраана. (macOS-ийн bash 3.2-т wait -n алга)
while kill -0 "$api" 2>/dev/null && kill -0 "$web" 2>/dev/null \
  && { [ "$mode" != "--phone" ] || { kill -0 "$ai" 2>/dev/null && kill -0 "$sip" 2>/dev/null; }; }; do
  sleep 1
done
