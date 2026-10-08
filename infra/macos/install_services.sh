#!/bin/bash
# Компьютер асахад бүх систем өөрөө асна (launchd, KeepAlive): утасны AI, SIP, backend, вэб, Cloudflare tunnel.
#
#   ./infra/macos/install_services.sh            # суулгах / шинэчлэх (вэбийг build хийнэ)
#   ./infra/macos/install_services.sh status     # төлөв
#   ./infra/macos/install_services.sh uninstall  # бүгдийг зогсоож устгах
#
# Тогтмол хаяг: https://pinequest-team-8.<account>.workers.dev (infra/cloudflare). Лог: ~/Library/Logs/pinequest/
# Эдгээр асаалттай үед ./dev.sh хэрэггүй (3000, 8100 порт эзэлнэ).
set -euo pipefail
ROOT="${PINEQUEST_ROOT:-$(cd "$(dirname "$0")/../.." && pwd)}"
LA="$HOME/Library/LaunchAgents"
LOGS="$HOME/Library/Logs/pinequest"
PY="$ROOT/.venv/bin/python"
NODEBIN="$(dirname "$(command -v node || ls -d "$HOME"/.nvm/versions/node/*/bin/node | tail -1)")"
SERVICES=(ai sip web frontend tunnel)
U="$(id -u)"

case "${1:-install}" in
  status)
    launchctl list | grep mn.pinequest || echo "суулгаагүй"
    exit 0 ;;
  uninstall)
    for s in "${SERVICES[@]}"; do
      launchctl bootout "gui/$U/mn.pinequest.$s" 2>/dev/null || true
      rm -f "$LA/mn.pinequest.$s.plist"
    done
    echo "устгалаа"
    exit 0 ;;
esac

# Tailscale-ийн IP (Zoiper-ийн domain); байхгүй бол sip_bridge өөрөө IP олно
TS="$HOME/.local/bin/tailscale"
HOST_IP="${HOST_IP:-$("$TS" --socket "$HOME/.local/share/tailscale/tailscaled.sock" ip -4 2>/dev/null | head -1 || true)}"
# tunnel: wrangler (KV-д хаяг бичнэ) — infra/cloudflare-д npm ci хийсэн байх ёстой
CF_DIR="${CLOUDFLARE_DIR:-$ROOT/infra/cloudflare}"
[ -x "$CF_DIR/node_modules/.bin/wrangler" ] || (cd "$CF_DIR" && PATH="$NODEBIN:$PATH" npm ci --silent)

echo "Вэб build..."
(cd "$ROOT/frontend" && PATH="$NODEBIN:$HOME/.bun/bin:$PATH" bun run build >/dev/null)
mkdir -p "$LOGS" "$LA"

plist() {  # нэр, хавтас, нэмэлт env (xml), тушаал...
  local s=$1 wd=$2 envx=$3; shift 3
  local args=""; for a in "$@"; do args="$args<string>$a</string>"; done
  cat > "$LA/mn.pinequest.$s.plist" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>mn.pinequest.$s</string>
  <key>ProgramArguments</key><array>$args</array>
  <key>WorkingDirectory</key><string>$wd</string>
  <key>EnvironmentVariables</key><dict><key>PATH</key><string>$NODEBIN:/usr/bin:/bin:/usr/sbin:/sbin</string>$envx</dict>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>
  <key>ThrottleInterval</key><integer>10</integer>
  <key>StandardOutPath</key><string>$LOGS/$s.log</string>
  <key>StandardErrorPath</key><string>$LOGS/$s.log</string>
</dict>
</plist>
EOF
  plutil -lint -s "$LA/mn.pinequest.$s.plist"
  reload "mn.pinequest.$s"
}

reload() {  # launchd хуучныг бүрэн суллахаас өмнө bootstrap хийвэл "5: Input/output error" -> хүлээж, дахин оролдоно
  local label=$1
  launchctl bootout "gui/$U/$label" 2>/dev/null || true
  for _ in $(seq 40); do launchctl print "gui/$U/$label" >/dev/null 2>&1 || break; sleep 0.5; done
  for try in 1 2 3 4 5; do
    launchctl bootstrap "gui/$U" "$LA/$label.plist" 2>/dev/null && return 0
    sleep 2
  done
  echo "$label асаж чадсангүй: launchctl bootstrap gui/$U $LA/$label.plist" >&2
  return 1
}

HOSTX=""; [ -n "$HOST_IP" ] && HOSTX="<key>HOST_IP</key><string>$HOST_IP</string>"
# Python-оор асаана: launchd-ээс шууд bash/node ажиллуулахад macOS Desktop хавтсанд хандахыг хориглож болно
plist ai       "$ROOT/backend" "$HOSTX" "$PY" -u "$ROOT/backend/run_ai.py" phone
plist sip      "$ROOT/backend" "$HOSTX" "$PY" -u "$ROOT/backend/run_ai.py" sip
plist web      "$ROOT" "" "$PY" -u "$ROOT/backend/app.py"
plist frontend "$ROOT/frontend" "<key>NODE_ENV</key><string>production</string>" \
  "$PY" -u "$ROOT/infra/macos/watchdog.py" "http://127.0.0.1:3000/login" -- \
  "$NODEBIN/node" "$ROOT/frontend/node_modules/next/dist/bin/next" start -p 3000 -H 127.0.0.1
plist tunnel   "$ROOT/backend/ai_runtime" \
  "<key>CLOUDFLARE_DIR</key><string>$CF_DIR</string><key>TUNNEL_URL</key><string>http://127.0.0.1:3000</string>" \
  "$PY" -u "$ROOT/backend/ai_runtime/scripts/tunnel.py"

echo "Асаалаа (${HOST_IP:-IP авто}). Төлөв: $0 status · Лог: $LOGS"
