"""Сануулгын дуудлагын яриа (залгагчаас үл хамаарна): мессеж -> товчлуур -> хариу.

  "...ирээрэй. Баталгаажуулах бол 1, цуцлах бол 2-ыг дарна уу."
    1 -> "Баярлалаа..."            -> confirmed
    2 -> "Ойлголоо, цуцаллаа..."    -> declined
    өөр товч / хариугүй -> дахин асууна (1 удаа) -> unconfirmed
Мессеж тоглож байхад дарсан товчийг ч хүлээн авна (сонсож дуусахыг хүлээхгүй).
"""
import numpy as np

from outbound.call import CallIO

WAIT_FIRST = 6      # мессежийн дараа хүлээх секунд
WAIT_REPEAT = 8


def run(io: CallIO, clips: dict[str, tuple[np.ndarray, int]]) -> tuple[str, list[str]]:
    """clips: message, repeat, confirmed, declined, no_input -> (wav, sr). -> (үр дүн, дарсан товчнууд)."""
    pressed: list[str] = []

    def ask(clip: str, wait: float) -> str | None:
        io.play(*clips[clip])
        got = io.collect(wait)
        pressed.extend(got)
        return next((d for d in got if d in "12"), None) or (got[0] if got else None)

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
