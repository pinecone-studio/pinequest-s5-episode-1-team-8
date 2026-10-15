"""Давхар дугаар шинэ бүртгэл, код, SMS, уулзалтын санал үүсгэхгүй."""
import os
import tempfile
import unittest
from unittest.mock import AsyncMock, Mock, patch

import db
from lead import LeadFlow
from phone_server import Call


class DuplicatePhoneTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.path = os.path.join(temp.name, "data", "receptionist.db")
        self.call = Call.__new__(Call)
        self.call.tenant = Mock(dir=temp.name, db_path=self.path, settings_path="unused")
        self.call.tenant.config.return_value = {"name": "Test", "lead_label": "Bootcamp"}
        self.call.uuid, self.call.lead_question = "call", None
        self.call.name_jobs, self.call.name_audio = [], None
        self.call.en = None
        self.call.history, self.call.dtmf = [], ""
        self.call.router = Mock(meta={"lead": {
            "already_registered": {"text": "Өмнө бүртгэлтэй хэрэглэгч байна."},
            "phone_retry": {"text": "Дахин дугаараа хэлнэ үү"}}})
        self.call.router.clip.return_value = ([], 8000)
        self.call.play, self.call.hangup = AsyncMock(), AsyncMock()
        self.call.log, self.call.arm_reprompt = Mock(), Mock()
        self.sms = self.enterContext(patch("phone_server.notify.send_registration_code"))
        self.staff = self.enterContext(patch("phone_server.notify.send"))
        self.code = self.enterContext(patch("phone_server.people.ensure_code", return_value="4720"))
        self.enterContext(patch("phone_server.people.docs"))

    def seed(self, phone="99112233", course=None, reason="lead"):
        return db.add_lead("previous", "Номин", phone, None, None, reason, course=course, path=self.path)

    def flow(self, phone="99112233", event=None, book=False):
        flow = LeadFlow("event" if event else "lead", "confirm", None, book=book)
        flow.name, flow.phone, flow.event = "Номин", phone, event
        self.call.lead = flow
        return flow

    def count(self):
        with db.connect(self.path) as con:
            return con.execute("SELECT COUNT(*) FROM leads").fetchone()[0]

    async def test_duplicate_stops_registration_and_booking(self):
        original = self.seed()
        flow = self.flow(book=True)
        await self.call.lead_turn("1")
        self.assertEqual(self.count(), 1)
        self.assertEqual(self.call.last_lead_id, original)
        self.assertEqual((flow.result, flow.saved, flow.save_pending), ("duplicate", False, False))
        self.assertIsNone(self.call.lead)
        self.assertEqual(self.call.log.call_args.args[1], "Өмнө бүртгэлтэй хэрэглэгч байна.")
        self.assertEqual(self.call.log.call_args.kwargs["route"], "lead_duplicate")
        self.sms.assert_not_called()
        self.staff.assert_not_called()
        self.code.assert_not_called()
        self.assertEqual(self.call.name_jobs, [])

    async def test_same_phone_in_another_event_is_also_duplicate(self):
        self.seed(course="Old event", reason="event")
        self.flow(event={"name": "New event"})
        await self.call.lead_turn("тийм")
        self.assertEqual(self.count(), 1)
        self.call.hangup.assert_not_awaited()
        self.sms.assert_not_called()

    async def test_rejected_phone_is_not_checked_or_saved(self):
        self.seed()
        flow = self.flow()
        await self.call.lead_turn("2")
        self.assertEqual(self.count(), 1)
        self.assertFalse(flow.duplicate)
        self.assertEqual(flow.state, "phone")
        self.code.assert_not_called()

    async def test_new_phone_is_registered(self):
        self.seed()
        flow = self.flow(phone="88776655")
        self.assertEqual(self.call.save_lead(flow), "4720")
        self.assertEqual(self.count(), 2)
        self.assertFalse(flow.duplicate)

    async def test_canceled_or_handoff_is_not_an_active_registration(self):
        original = self.seed()
        with db.connect(self.path) as con:
            con.execute("UPDATE leads SET status='canceled' WHERE id=?", (original,))
        self.seed(reason="handoff")
        self.assertIsNone(db.active_lead("99112233", path=self.path))
        self.assertEqual(self.call.save_lead(self.flow()), "4720")
        self.assertEqual(self.count(), 3)


if __name__ == "__main__":
    unittest.main()
