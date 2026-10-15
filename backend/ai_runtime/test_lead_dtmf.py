"""Registration keypad flow without models, audio or external services."""
import asyncio
import unittest
from unittest.mock import AsyncMock, Mock

from lead import LeadFlow, pair_word, yes_no
from phone_server import Call


class LeadDtmfTest(unittest.IsolatedAsyncioTestCase):
    def make_call(self, state="confirm", lang="mn"):
        call = Call.__new__(Call)
        call.lead = LeadFlow("lead", state, None, lang=lang)
        call.lead.phone = "99112233"
        call.account = None
        call.dtmf = ""
        call.dtmf_at = 0.0
        call.reprompt = None
        call.turn = None
        call.flush = Mock()
        call.log = Mock()

        async def lead_turn(text):
            call.lead.handle(text)
        call.lead_turn = AsyncMock(side_effect=lead_turn)
        return call

    async def test_confirmation_keys_in_both_languages(self):
        for lang in ("mn", "en"):
            for key in ("1", "2"):
                with self.subTest(lang=lang, key=key):
                    call = self.make_call(lang=lang)
                    call.on_dtmf(key)
                    await call.turn
                    self.assertEqual(call.lead.result, "saved" if key == "1" else None)
                    self.assertEqual(call.lead.phone, "99112233" if key == "1" else None)

    async def test_replacement_phone_still_enters_confirmation(self):
        call = self.make_call()
        for key in "88776655":
            call.on_dtmf(key)
        await call.turn
        self.assertEqual(call.lead.phone, "88776655")
        self.assertEqual(call.lead.state, "confirm")

    async def test_phone_digits_during_prompt_are_not_lost(self):
        call = self.make_call(state="phone")
        done = asyncio.Event()
        call.turn = asyncio.create_task(done.wait())
        for key in "99112233":
            call.on_dtmf(key)
        queued = call.turn
        await asyncio.sleep(0)
        call.lead_turn.assert_not_awaited()
        done.set()
        await queued
        call.lead_turn.assert_awaited_once_with("99112233")
        self.assertEqual(call.lead.state, "confirm")

    async def test_digits_typed_during_name_step_are_kept(self):
        # Нэрийг таниулж байх зуур "88" дарсан -> өмнө нь гээгдэж "00843288" болж байсан
        call = self.make_call(state="name")
        for key in "88":
            call.on_dtmf(key)
        self.assertEqual(call.dtmf, "88")
        call.lead.state = "phone"
        for key in "008432":
            call.on_dtmf(key)
        await call.turn
        call.lead_turn.assert_awaited_once_with("88008432")

    async def test_long_pause_restarts_number(self):
        call = self.make_call(state="phone")
        for key in "008432":
            call.on_dtmf(key)
        call.dtmf_at -= 10                 # хагас бичээд удаан хүлээсэн, дахин эхнээс нь бичнэ
        for key in "88008432":
            call.on_dtmf(key)
        await call.turn
        call.lead_turn.assert_awaited_once_with("88008432")

    def test_filler_is_not_a_name(self):
        flow = LeadFlow("lead", "name", None)
        self.assertEqual(flow.handle("юм уу"), ["ask_name_again"])
        self.assertEqual(flow.state, "name")
        self.assertEqual(flow.handle("Билэгсайхан"), ["ask_phone"])
        self.assertEqual(flow.name, "Билэгсайхан")

    def test_filler_name_is_never_saved(self):
        flow = LeadFlow("lead", "name", None)
        for text in ("юу", "юу", "99112233", "Миний нэр", "..."):
            self.assertEqual(flow.handle(text), ["ask_name_again"])
            self.assertEqual(flow.state, "name")
            self.assertIsNone(flow.name)

    def test_spoken_name_is_cleaned(self):
        for text, expected in (("За, намайг Батболд гэдэг юм аа", "Батболд"),
                               ("Сайн байна уу. Миний нэр Номин-Эрдэнэ", "Номин-Эрдэнэ"),
                               ("Би Доржийн Энхтүвшин байна", "Доржийн Энхтүвшин"),
                               ("  оюун-эрдэнэ  ", "Оюун-Эрдэнэ")):
            with self.subTest(text=text):
                flow = LeadFlow("lead", "name", None)
                self.assertEqual(flow.handle(text), ["ask_phone"])
                self.assertEqual(flow.name, expected)

    async def test_silent_caller_gets_question_again(self):
        # AI ярьж байхад "зөв" гэвэл алга болдог -> чимээгүй бол асуултаа давтана, товчлуур дарвал үгүй
        import phone_server
        phone_server.REPROMPT_AFTER = 0.05
        for pressed in (False, True):
            call = self.make_call()
            call.closed, call.hearing, call.out, call.last_out = False, False, bytearray(), 0.0
            call.play = AsyncMock()
            call.arm_reprompt([("wav", 8000)])
            if pressed:
                call.on_dtmf("1")
            await asyncio.sleep(0.15)
            self.assertEqual(call.play.await_count, 0 if pressed else 1)

    def test_near_speech_drops_background_before_caller(self):
        # Ард яриа (0.02) -> залгагч "зөв" (0.15) -> ард яриа: зөвхөн залгагчийн хэсэг (+0.3с) үлдэнэ
        import numpy as np
        from phone_server import near_speech
        sec = 0.032
        levels = [0.02] * 30 + [0.15, 0.12, 0.02, 0.14] + [0.02] * 30
        chunks = [np.full(256, lv, np.float32) for lv in levels]
        out = near_speech(chunks, levels, 0.15, sec)
        pad = int(0.3 / sec)
        self.assertEqual(len(out), (4 + 2 * pad) * 256)
        self.assertAlmostEqual(float(out[(pad + 2) * 256]), 0.02 * 0.25, places=5)   # дотор сул -> 0.25

    def test_unclear_confirmation_keeps_phone(self):
        # Бодит дуудлагаас: "зөв"-ийг STT "байна уу", "гэсэн" гэж сонссон -> дугаар устаж байсан
        flow = LeadFlow("lead", "confirm", None)
        flow.phone = "88008432"
        self.assertEqual(flow.handle("байна уу"), ["readback", "digits:88008432", "confirm"])
        self.assertEqual(flow.phone, "88008432")
        self.assertEqual(flow.handle("1"), ["done"])
        self.assertEqual(flow.result, "saved")

    def test_misheard_zuv_is_yes(self):
        for text in ("төв дүү", "зөвөө"):
            with self.subTest(text=text):
                flow = LeadFlow("lead", "confirm", None)
                flow.phone = "88008432"
                self.assertEqual(flow.handle(text), ["done"])

    def test_no_after_retry_asks_phone_again(self):
        flow = LeadFlow("lead", "confirm", None)
        flow.phone = "88008432"
        flow.handle("гэсэн")
        self.assertEqual(flow.handle("гэсэн"), ["phone_retry"])
        self.assertIsNone(flow.phone)
        self.assertEqual(flow.handle("88008432"), ["readback", "digits:88008432", "confirm"])
        self.assertEqual(flow.handle("байна уу"), ["readback", "digits:88008432", "confirm"])

    def test_numeric_yes_no(self):
        self.assertIs(yes_no("1"), True)
        self.assertIs(yes_no("2"), False)
        self.assertIsNone(yes_no("99112233"))


class VoiceYesNoTest(unittest.TestCase):
    def test_spoken_answers(self):
        for t in ("тийм ээ", "за очно", "ирнэ ээ", "мэдээж бүртгүүлнэ", "тэгээрэй"):
            self.assertIs(yes_no(t), True, t)
        for t in ("үгүй", "амжихгүй нээ", "очихгүй", "чадахгүй байх", "бүртгүүлэхгүй", "дараа"):
            self.assertIs(yes_no(t), False, t)
        for t in ("мэдэхгүй", "хэдэн цагт болох вэ", "хаана болох вэ", "ойлгосонгүй"):
            self.assertIsNone(yes_no(t), t)


class InterruptTest(unittest.IsolatedAsyncioTestCase):
    async def test_keypress_cuts_current_speech(self):
        speaking = asyncio.create_task(asyncio.sleep(10))   # эвентийн огноог уншиж байна
        await asyncio.sleep(0)
        await Call.interrupt(speaking)
        self.assertTrue(speaking.cancelled())


class PairWordTest(unittest.TestCase):
    def test_phone_read_in_pairs(self):
        self.assertEqual([pair_word(p) for p in ("85", "22", "26", "34")],
                         ["наян тав", "хорин хоёр", "хорин зургаа", "гучин дөрөв"])
        self.assertEqual([pair_word(p) for p in ("08", "00", "10", "20", "11")],
                         ["тэг найм", "тэг тэг", "арав", "хорь", "арван нэг"])

    def test_digits_audio_uses_pairs(self):
        call = Call.__new__(Call)
        clip = lambda c: (__import__("numpy").ones(10, "float32"), 24000)  # noqa: E731
        call.router = Mock(meta={"pairs": {f"{i:02d}": f"p{i:02d}" for i in range(100)},
                                 "digits": [f"d{i}" for i in range(10)]}, clip=Mock(side_effect=clip))
        call.digits_audio("85222634")
        self.assertEqual([c.args[0] for c in call.router.clip.call_args_list], ["p85", "p22", "p26", "p34"])


if __name__ == "__main__":
    unittest.main()
