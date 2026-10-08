"""
launchd-ийн KeepAlive зөвхөн процесс бүрэн гарвал дахин асаадаг. `next start` SIGTERM авсны дараа портоо хааж
амьд үлдэх тохиолдол гарсан (вэб 503) -> энэ хянагч тушаалыг ажиллуулж, хаяг хариу өгөхгүй болбол бүх процессыг
унтрааж гарна, launchd дахин асаана.

  python watchdog.py http://127.0.0.1:3000/login -- node next start -p 3000
"""
import os
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.request

GRACE, EVERY, MAX_FAILS = 30, 10, 3


def alive(url: str) -> bool:
    try:
        urllib.request.urlopen(url, timeout=10)
        return True
    except urllib.error.HTTPError as e:
        return e.code < 500
    except Exception:
        return False


def main():
    url, cmd = sys.argv[1], sys.argv[sys.argv.index("--") + 1:]
    proc = subprocess.Popen(cmd, start_new_session=True)

    def stop(*_):
        try:
            os.killpg(proc.pid, signal.SIGTERM)
            proc.wait(timeout=10)
        except (ProcessLookupError, subprocess.TimeoutExpired):
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        sys.exit(1)

    signal.signal(signal.SIGTERM, stop)
    time.sleep(GRACE)
    fails = 0
    while proc.poll() is None:
        fails = 0 if alive(url) else fails + 1
        if fails >= MAX_FAILS:
            print(f"[watchdog] {url} {MAX_FAILS} удаа хариу өгсөнгүй -> дахин асаана", flush=True)
            stop()
        time.sleep(EVERY)
    sys.exit(proc.returncode or 1)


if __name__ == "__main__":
    main()
