"""Давтан дуудлага өмнөх бүртгэлийг ашиглаж, өөр хөтөлбөрийг хаахгүй."""
import os
import tempfile
import unittest
from unittest.mock import AsyncMock, Mock, patch

import db
import people
from lead import LeadFlow
from phone_server import Call


class DuplicateRegistrationTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = os.path.join(self.temp.name, "data", "receptionist.db")
        self.call = Call.__new__(Call)
        self.call.tenant = Mock(dir=self.temp.name, db_path=self.path, settings_path="unused")
        self.call.tenant.config.return_value = {"name": "Test", "lead_label": None}
        self.call.uuid, self.call.lead_question = "call", None
        self.call.name_jobs, self.call.name_audio = [], None
        self.send = patch("phone_server.notify.send", return_value=True).start()
        self.sms = patch("phone_server.notify.send_registration_code", return_value=True).start()
        self.addCleanup(patch.stopall)

    def flow(self, reason="lead", phone="99112233", event=None):
        flow = LeadFlow(reason, "confirm", None)
        flow.name, flow.phone, flow.event = "Номин", phone, event
        return flow

    def count(self):
        with db.connect(self.path) as con:
            return con.execute("SELECT COUNT(*) FROM leads").fetchone()[0]

    async def test_repeat_registration_reuses_record_and_code(self):
        for course in (None, "Bootcamp"):
            self.call.tenant.config.return_value["lead_label"] = course
            first = self.call.save_lead(self.flow())
            lead_id, count = self.call.last_lead_id, self.count()
            jobs = len(self.call.name_jobs)
            repeat = self.flow()
            repeat.name = "Нөмийн"
            self.assertEqual(self.call.save_lead(repeat), first)
            self.assertTrue(repeat.duplicate)
            self.assertEqual(self.call.last_lead_id, lead_id)
            self.assertEqual(self.count(), count)
            self.assertEqual(len(self.call.name_jobs), jobs)
            self.assertEqual(people.lead(self.temp.name, lead_id)["name"], "Номин")

    async def test_other_course_phone_and_canceled_registration_are_allowed(self):
        self.call.save_lead(self.flow())
        original = self.call.last_lead_id
        self.call.save_lead(self.flow(phone="88776655"))
        self.call.save_lead(self.flow("event", event={"name": "Hackathon"}))
        self.assertEqual(self.count(), 3)
        with db.connect(self.path) as con:
            con.execute("UPDATE leads SET status='canceled' WHERE id=?", (original,))
        flow = self.flow()
        self.call.save_lead(flow)
        self.assertFalse(flow.duplicate)
        self.assertEqual(self.count(), 4)

    async def test_handoff_does_not_block_registration(self):
        self.call.save_lead(self.flow("handoff"))
        flow = self.flow()
        self.call.save_lead(flow)
        self.assertFalse(flow.duplicate)
        self.assertEqual(self.count(), 2)

    async def test_no_phone_does_not_merge_different_people(self):
        self.call.save_lead(self.flow(phone=None))
        self.call.save_lead(self.flow(phone=None))
        self.assertEqual(self.count(), 2)

    async def test_duplicate_reply_and_booking_use_existing_registration(self):
        self.call.save_lead(self.flow())
        lead_id = self.call.last_lead_id
        self.call.en = None
        self.call.router = Mock(meta={"lead": {
            "already": {"text": "Already registered"},
            "already_book": {"text": "Already registered. Book?"}}})
        self.call.router.clip.return_value = ([], 8000)
        self.call.play = AsyncMock()
        self.call.log = Mock()
        self.call.arm_reprompt = Mock()
        self.call.history, self.call.dtmf = [], ""
        for book in (False, True):
            self.call.lead = flow = self.flow()
            flow.book = book
            await self.call.lead_turn("тийм")
            self.assertEqual(self.count(), 1)
            self.assertEqual(self.call.last_lead_id, lead_id)
            self.assertTrue(flow.duplicate)
            self.assertEqual(self.call.log.call_args.args[1],
                             "Already registered. Book?" if book else "Already registered")
            if book:
                self.assertEqual(flow.handle("1"), ["@book"])


if __name__ == "__main__":
    unittest.main()
