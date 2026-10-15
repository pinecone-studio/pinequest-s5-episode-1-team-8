"""Single-digit STT choices pass through only in supported registration states."""
import unittest
from unittest.mock import AsyncMock, Mock

import numpy as np

from lead import LeadFlow
from phone_server import Call


class SpokenChoiceTest(unittest.IsolatedAsyncioTestCase):
    def call_for(self, text, state):
        call = Call.__new__(Call)
        call.lead = LeadFlow("lead", state, None)
        call.lead.phone = "99112233"
        call.lead.events = [{"name": "First", "at": "2026-10-20T10:00"},
                            {"name": "Second", "at": "2026-10-21T10:00"}]
        call.account, call.en = None, None
        call.m = Mock(stt_pool=None)
        call.transcribe = Mock(return_value=(text, "mn"))
        call.hold_while, call.log = AsyncMock(), Mock()

        async def lead_turn(answer):
            call.lead.handle(answer)
            return True

        call.lead_turn = AsyncMock(side_effect=lead_turn)
        return call

    async def test_confirmation_and_event_choices_reach_flow(self):
        for text, state, next_state, result in [
            ("1", "confirm", "confirm", "saved"),
            ("2", "confirm", "phone", None),
            ("1.", "confirm", "confirm", "saved"),
            ("1", "event_pick", "event_offer", None),
            ("2", "event_pick", "event_offer", None),
            ("1", "event_offer", "name", None),
            ("2", "event_offer", "event_offer", "declined"),
            ("1", "book_offer", "book_offer", "book"),
        ]:
            with self.subTest(text=text, state=state):
                call = self.call_for(text, state)
                await call.handle_utterance(np.zeros(800, np.float32))
                call.lead_turn.assert_awaited_once_with(text)
                self.assertEqual((call.lead.state, call.lead.result), (next_state, result))
                if state == "event_pick":
                    self.assertEqual(call.lead.event, call.lead.events[int(text) - 1])

    async def test_single_character_noise_is_still_ignored(self):
        for text, state in [("1", "name"), ("1", "phone"), ("3", "confirm"), ("а", "confirm")]:
            with self.subTest(text=text, state=state):
                call = self.call_for(text, state)
                await call.handle_utterance(np.zeros(800, np.float32))
                call.lead_turn.assert_not_awaited()
                call.log.assert_not_called()


if __name__ == "__main__":
    unittest.main()
