"""Registration keypad flow without models, audio or external services."""
import asyncio
import unittest
from unittest.mock import AsyncMock, Mock

from lead import LeadFlow, yes_no
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

    def test_filler_name_accepted_after_one_retry(self):
        flow = LeadFlow("lead", "name", None)
        flow.handle("юу")
        self.assertEqual(flow.handle("юу"), ["ask_phone"])

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


if __name__ == "__main__":
    unittest.main()
