"""Repeat the latest spoken turn without restarting registration or booking."""
import unittest
from unittest.mock import AsyncMock, Mock, patch

import numpy as np

from lead import LeadFlow
from phone_server import Call, REPEAT_LAST


class RepeatLastTest(unittest.IsolatedAsyncioTestCase):
    def make_call(self):
        call = Call.__new__(Call)
        call.lead, call.account, call.en = None, None, None
        call.lang, call.en_misses = "mn", 0
        call.history, call.dtmf = [], ""
        call.uuid = None
        call.last_reply, call.last_reply_text = [("greeting", 24000)], "Мэндчилгээ"
        call.m = Mock(stt_pool=None)
        call.play, call.hold_while = AsyncMock(), AsyncMock()
        call.log, call.arm_reprompt = Mock(), Mock()
        call.router = Mock()
        call.router.meta = {"lead": {
            "ask_name_again": {"text": "Нэрээ хэлнэ үү"},
            "ask_phone": {"text": "Дугаараа хэлнэ үү"},
            "event_list": {"text": "Арга хэмжээнүүд"},
            "event_pick": {"text": "Алийг сонгох вэ?"},
            "ord_1": {"text": "Нэгдүгээрт"},
            "ord_2": {"text": "Хоёрдугаарт"},
        }, "account": {"menu": {"text": "Бүртгэлээ өөрчлөх үү?"}}}
        call.router.clip.side_effect = lambda item: (item["text"], 24000)
        return call

    async def repeat(self, call, text="дахиад хэлдээ"):
        expected = list(call.last_reply)
        call.play.reset_mock()
        call.transcribe = Mock(return_value=(text, "mn"))
        with patch("phone_server.respond", new_callable=AsyncMock) as respond:
            await call.handle_utterance(np.zeros(800, np.float32))
            respond.assert_not_awaited()
        self.assertEqual([c.args for c in call.play.await_args_list], expected)
        self.assertNotIn("greeting", [c.args[0] for c in call.play.await_args_list])

    async def test_registration_repeats_latest_prompt_without_consuming_name(self):
        call = self.make_call()
        flow = call.lead = LeadFlow("lead", "offer", None)
        await call.lead_turn("тийм")
        self.assertEqual(call.last_reply_text, "Нэрээ хэлнэ үү")
        await self.repeat(call)
        self.assertEqual((flow.state, flow.name), ("name", None))
        await call.lead_turn("Номин")
        self.assertEqual(call.last_reply_text, "Дугаараа хэлнэ үү")
        for text in ("Дахин хэлж өгөөч", "давтаад хэлээч", "дахиад нэг хэлээд өгөөч"):
            await self.repeat(call, text)
        self.assertEqual((flow.state, flow.phone_tries), ("phone", 0))

    async def test_event_list_repeats_without_changing_selection(self):
        call = self.make_call()
        flow = call.lead = LeadFlow("event", "event_start", None, events=[
            {"name": "Demo", "at": "2026-10-20T10:00"},
            {"name": "Hackathon", "at": "2026-10-21T10:00"},
        ])
        with patch("phone_server.people.slot_parts", return_value=[]):
            await call.lead_turn("эвентэд бүртгүүлмээр байна")
        self.assertEqual(len(call.last_reply), 4)
        await self.repeat(call)
        self.assertEqual((flow.state, flow.pick_tries, flow.event), ("event_pick", 0, None))

    async def test_account_prompt_is_remembered_without_consuming_input(self):
        call = self.make_call()
        flow = call.account = Mock(state="menu", events=[], finished=False)
        await call.play_account(flow, ["menu"], "бүртгэлээ шалгая")
        self.assertEqual(call.last_reply_text, "Бүртгэлээ өөрчлөх үү?")
        await self.repeat(call)
        flow.handle.assert_not_called()
        self.assertIs(call.account, flow)

    async def test_english_answer_replaces_greeting(self):
        call = self.make_call()
        call.en = Mock()
        call.en.respond.return_value = {"route": "faq", "score": 1.0, "text": "Latest answer", "clip": {}}
        call.en.clip.return_value = ("english audio", 24000)
        await call.en_turn("question", 0)
        await self.repeat(call)
        self.assertEqual(call.last_reply_text, "Latest answer")

    async def test_latest_normal_answer_replaces_previous_reply(self):
        call = self.make_call()
        call.router.meta = {"fillers": [], "holds": []}
        call.maybe_start_lead, call.maybe_start_account = Mock(), Mock()
        call.transcribe = Mock(return_value=("сургалт хэд вэ", "mn"))

        async def respond(*args, play_fn, meta):
            meta["route"] = "faq"
            await play_fn("latest audio", 24000)
            return "Хамгийн сүүлийн хариу"

        with patch("phone_server.respond", side_effect=respond):
            await call.handle_utterance(np.zeros(800, np.float32))
        self.assertEqual(call.last_reply_text, "Хамгийн сүүлийн хариу")
        await self.repeat(call)

    def test_other_requests_are_not_repeat_commands(self):
        for text in ("дахин бүртгүүлмээр байна", "дахиад залгана", "нэг", "сургалт хэдэн төгрөг вэ"):
            self.assertIsNone(REPEAT_LAST.search(text))


if __name__ == "__main__":
    unittest.main()
