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

    def test_numeric_yes_no(self):
        self.assertIs(yes_no("1"), True)
        self.assertIs(yes_no("2"), False)
        self.assertIsNone(yes_no("99112233"))


if __name__ == "__main__":
    unittest.main()
