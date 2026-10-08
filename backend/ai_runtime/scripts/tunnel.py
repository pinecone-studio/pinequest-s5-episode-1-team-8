"""
Cloudflare quick tunnel (вэб удирдлага -> https://*.trycloudflare.com) + тогтмол хаяг.

Quick tunnel-ийн хаяг асах бүрт солигддог -> шинэ хаягийг Worker-ийн KV ("origin")-д бичнэ, тэгэхээр хэрэглэгчид
https://sim-trunk.<account>.workers.dev (cloudflare/worker.js) хэвээр ашиглана. services.sh-ийн "tunnel" үйлчилгээ.

Quick tunnel-д баталгаа байхгүй: Cloudflare ~2 цагийн дараа устгасан ("Unauthorized: Tunnel not found"), cloudflared
үхсэн tunnel руу дахин дахин холбогдсоор, шинэ хаяг авдаггүй (10-06). Тиймээс энд хянана: тэр алдаа гарах эсвэл
хаяг 3 минут дараалан хариу өгөхгүй бол cloudflared-ийг дахин асааж шинэ хаяг авна.

Python дээр бичсэн шалтгаан: launchd-ээс /bin/bash-аар ажиллуулахад macOS Desktop хавтсанд хандахыг хориглосон
("Operation not permitted"); .venv-ийн python-д тэр зөвшөөрөл бусад үйлчилгээнээс аль хэдийн бий.
"""
import glob
import os
import re
import signal
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# Код backend/ai_runtime-д, Cloudflare deployment infra/cloudflare-д хадгалагдана.
SOURCE_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.realpath(__file__)))))
CF_DIR = os.path.abspath(os.getenv("CLOUDFLARE_DIR") or os.path.join(SOURCE_ROOT, "infra", "cloudflare"))
WRANGLER = os.path.join(CF_DIR, "node_modules", ".bin", "wrangler")
CLOUDFLARED = os.path.expanduser("~/.local/bin/cloudflared")
URL = re.compile(r"https://[a-z0-9-]+\.trycloudflare\.com")
DEAD = ("Tunnel not found",)            # Cloudflare tunnel-ийг устгасан -> шинэ tunnel хэрэгтэй
CHECK_EVERY, MAX_FAILS = 60, 3
NODE_BIN = sorted(glob.glob(os.path.expanduser("~/.nvm/versions/node/*/bin")))[-1:]
ENV = {**os.environ, "PATH": ":".join(NODE_BIN + [os.environ.get("PATH", "")])}
current: subprocess.Popen | None = None


def log(msg: str):
    print(f"[tunnel] {time.strftime('%H:%M:%S')} {msg}", flush=True)


def publish(url: str):
    """Worker-ийн KV-д одоогийн хаягийг бичнэ (wrangler-ийн OAuth нэвтрэлтээр)."""
    if not os.path.exists(WRANGLER):
        log("wrangler алга (cd cloudflare && npm install)")
        return
    r = subprocess.run([WRANGLER, "kv", "key", "put", "origin", url, "--binding", "ORIGIN", "--remote"],
                       cwd=CF_DIR, env=ENV, capture_output=True, text=True, timeout=120)
    if r.returncode == 0:
        log(f"тогтмол хаяг -> {url}")
    else:
        log(f"KV-д бичиж чадсангүй (cd cloudflare && npx wrangler login): {r.stderr[-300:]}")


def alive(url: str) -> bool:
    try:
        urllib.request.urlopen(f"{url}/login", timeout=20)
        return True
    except urllib.error.HTTPError as e:
        return e.code < 500                # 530/502 = tunnel ажиллахгүй
    except Exception:
        return False


def watch(proc: subprocess.Popen, state: dict):
    """Хаяг ажиллахгүй болвол cloudflared-ийг зогсооно -> main() шинэ tunnel асаана."""
    fails = 0
    while proc.poll() is None:
        time.sleep(CHECK_EVERY)
        if not state.get("url") or proc.poll() is not None:
            continue
        fails = 0 if alive(state["url"]) else fails + 1
        if fails >= MAX_FAILS:
            log(f"{state['url']} {MAX_FAILS} удаа хариу өгсөнгүй -> шинэ tunnel")
            proc.terminate()
            return


def run_once():
    global current
    # http2: сургуулийн сүлжээ QUIC (UDP 7844)-ийг хаадаг байж болно
    web_url = os.getenv("TUNNEL_URL", "http://localhost:3000")
    proc = current = subprocess.Popen([CLOUDFLARED, "tunnel", "--no-autoupdate", "--protocol", "http2",
                                       "--url", web_url],
                                      stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
    state: dict = {}
    threading.Thread(target=watch, args=(proc, state), daemon=True).start()
    for line in proc.stdout:
        print(line, end="", flush=True)
        m = URL.search(line)
        if m and not state.get("url"):
            state["url"] = m.group(0)
            publish(state["url"])
        if any(d in line for d in DEAD) and proc.poll() is None:
            log("Cloudflare tunnel-ийг устгасан -> шинэ tunnel")
            proc.terminate()
    proc.wait()


def stop(*_):
    if current and current.poll() is None:      # launchd зогсооход cloudflared-ийг хамт унтраана
        current.terminate()
    sys.exit(0)


def main():
    signal.signal(signal.SIGTERM, stop)
    while True:
        run_once()
        log("cloudflared зогслоо, 5с-ийн дараа дахин асаана")
        time.sleep(5)


if __name__ == "__main__":
    main()
