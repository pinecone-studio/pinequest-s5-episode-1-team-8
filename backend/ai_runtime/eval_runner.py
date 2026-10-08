"""
Хариултын нарийвчлалын шалгалт: tests/eval_questions.json (асуулт -> хүлээгдэж буй хариулт).

scripts/train_selector.py сургасан сонгогчийг идэвхжүүлэхийн өмнө дүрмийн замтай харьцуулахад дуудна.
"""
import contextlib
import io
import json
import os

import tenant as tenants


async def run_eval(router=None, quiet: bool = False, eval_file: str | None = None):
    """-> (зөв, нийт, буруу [(case, reply, meta)])."""
    from stream_voice import FAQRouter, respond
    t = tenants.current()
    eval_file = eval_file or (t.eval_path if os.path.exists(t.eval_path) else t.auto_eval_path)
    cases = json.load(open(eval_file, encoding="utf-8"))["questions"]
    router = router or FAQRouter()
    special = {"REPEAT": router.repeat()["text"], "CLARIFY": router.clarify()["text"],
               "HANDOFF": router.error()["text"]}

    async def silent(wav, sr):
        pass

    ok, rows = 0, []
    for case in cases:
        meta: dict = {}
        history = []
        for prev in case.get("history", []):
            history += [{"role": "user", "content": "..."}, {"role": "assistant", "content": special.get(prev, prev)}]
        out = io.StringIO()
        with contextlib.redirect_stdout(out) if quiet else contextlib.nullcontext():
            reply = await respond(case["q"], history, router, None, None, play_fn=silent, meta=meta)
        expects = case["expect"] if isinstance(case["expect"], list) else [case["expect"]]
        good = any(special.get(e, e) in reply for e in expects)
        ok += good
        if not good:
            rows.append((case, reply, meta))
    if not quiet:
        for case, reply, meta in rows:
            print(f"    ✗ '{case['q']}'\n        хүлээсэн: {case['expect']}\n"
                  f"        гарсан:   [{meta.get('route')}] {reply[:90]}")
        print(f"  хариултын нарийвчлал {ok}/{len(cases)}")
    return ok, len(cases), rows


if __name__ == "__main__":
    import asyncio
    asyncio.run(run_eval())
