"""Сануулгын дуудлагын яриа (залгагчаас үл хамаарна): мессеж -> яриа ЭСВЭЛ товчлуур -> хариу.

  "...Та ирэх хэвээрээ юу?"
    «тийм», «ирнэ», «очно» / 1        -> "Баярлалаа..."         -> confirmed
    «үгүй», «амжихгүй», «ирэхгүй» / 2 -> "Ойлголоо, цуцаллаа..." -> declined
    ойлгомжгүй / хариугүй -> дахин асууна (1 удаа) -> unconfirmed
Яриаг утасны AI серверийн STT-ээр (127.0.0.1 REVIEW_PORT /stt) таниулна — вэб процесст загвар ачаалахгүй.
"""
import base64
import json
import os
import re
import urllib.request

import numpy as np

from outbound.call import CallIO

STT_URL = f"http://127.0.0.1:{os.getenv('REVIEW_PORT', '9093')}/stt"
# ai_runtime/lead.py yes_no-тэй ижил үгс (вэб процесс AI runtime-ийг импортлохгүй)
YES = {"тийм", "за", "зөв", "мөн", "тиймээ", "болно", "тэгье", "тэгнэ", "ирнэ", "ирье", "очно", "очъё", "очье",
       "мэдээж", "ирэх", "очих", "баталгаажуул", "баталгаажуулна", "тэгээрэй", "ок"}
NO = {"үгүй", "биш", "болохгүй", "хэрэггүй", "цуцал", "цуцлаарай", "цуцална", "битгий", "дараа", "амжихгүй",
      "чадахгүй", "ирэхгүй", "очихгүй"}
UNSURE = {"мэдэхгүй", "ойлгохгүй", "ойлгосонгүй", "сонсогдохгүй"}


def spoken_answer(text: str) -> str | None:
    """Яриа -> "1" (ирнэ) / "2" (ирэхгүй) / None."""
    words = set(re.findall(r"[а-яөүёa-z]+", (text or "").lower()))
    if not words or words & UNSURE:
        return None
    if words & NO or any(w.endswith("хгүй") for w in words):
        return "2"
    if words & YES:
        return "1"
    return None


def transcribe(audio: np.ndarray) -> str:
    pcm = (np.clip(audio, -1, 1) * 32767).astype("<i2").tobytes()
    req = urllib.request.Request(STT_URL, data=json.dumps({"audio": base64.b64encode(pcm).decode(), "sr": 8000}).encode(),
                                 headers={"content-type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return json.load(r).get("text", "")
    except Exception as exc:                 # AI сервер унтарсан -> товчлуур хэвээр ажиллана
        print(f"  [сануулга] яриа таних боломжгүй: {exc}")
        return ""

WAIT_FIRST = 6      # мессежийн дараа хүлээх секунд
WAIT_REPEAT = 8


def run(io: CallIO, clips: dict[str, tuple[np.ndarray, int]]) -> tuple[str, list[str]]:
    """clips: message, repeat, confirmed, declined, no_input -> (wav, sr). -> (үр дүн, дарсан товчнууд)."""
    pressed: list[str] = []

    heard: list[str] = []

    def ask(clip: str, wait: float) -> str | None:
        io.play(*clips[clip])
        got, speech = io.listen(wait)
        pressed.extend(got)
        key = next((d for d in got if d in "12"), None) or (got[0] if got else None)
        if key is None and speech is not None:
            text = transcribe(speech)
            heard.append(text)
            key = spoken_answer(text)
            print(f"  [сануулга] яриа: {text!r} -> {key}")
            if key:
                pressed.append(f"яриа:{text}")
        return key

    answer = ask("message", WAIT_FIRST)
    if answer not in ("1", "2") and not io.ended.is_set():
        answer = ask("repeat", WAIT_REPEAT)
    if io.ended.is_set() and answer not in ("1", "2"):
        return "hung_up", pressed
    if answer == "1":
        io.play(*clips["confirmed"])
        return "confirmed", pressed
    if answer == "2":
        io.play(*clips["declined"])
        return "declined", pressed
    io.play(*clips["no_input"])
    return "unconfirmed", pressed
