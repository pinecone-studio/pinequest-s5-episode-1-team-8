"""Чимэгэ холболтыг төлбөртэй API дуудахгүйгээр шалгана."""
import io
import os
import unittest
import wave
from unittest.mock import AsyncMock, Mock, patch

import httpx
import numpy as np

import stt
from phone_server import Call


class ChimegeTest(unittest.TestCase):
    @patch("stt.time.sleep")
    @patch("stt.httpx.get")
    @patch("stt.httpx.post")
    def test_pcm_wav_and_token(self, post, get, sleep):
        request = httpx.Request("POST", "https://example.test")
        post.return_value = httpx.Response(200, json={"uuid": "test-job"}, request=request)
        get.side_effect = [httpx.Response(200, json={"done": False}, request=request),
                           httpx.Response(200, json=[{"done": True, "transcription": "батболд"}], request=request)]
        self.assertEqual(stt.ChimegeSTT("test-token").transcribe(np.full(8000, 0.25, np.float32), 8000), "батболд")
        args, kw = post.call_args
        self.assertEqual(args[0], "https://api.chimege.com/v1.2/stt-long")
        self.assertEqual(kw["headers"]["Token"], "test-token")
        self.assertEqual(kw["timeout"], 15)
        self.assertEqual(get.call_count, 2)
        self.assertEqual(sleep.call_count, 2)
        self.assertEqual(get.call_args.args[0], "https://api.chimege.com/v1.2/stt-long-transcript")
        self.assertEqual(get.call_args.kwargs["headers"], {"Token": "test-token", "UUID": "test-job"})
        with wave.open(io.BytesIO(kw["content"])) as wav:
            self.assertEqual((wav.getnchannels(), wav.getsampwidth(), wav.getframerate(), wav.getnframes()),
                             (1, 2, 16000, 16000))

    @patch("stt.httpx.post")
    def test_silence_and_warmup_cost_nothing(self, post):
        engine = stt.ChimegeSTT("test-token")
        engine.warmup()
        self.assertEqual(engine.transcribe(np.zeros(8000, np.float32), 8000), "")
        self.assertEqual(engine.transcribe(np.array([], np.float32), 8000), "")
        post.assert_not_called()

    @patch("stt.httpx.post")
    def test_invalid_audio_does_not_reach_api(self, post):
        for audio, sr in ((np.ones((2, 2)), 8000), (np.array([np.nan]), 8000), (np.ones(1), 0)):
            with self.assertRaises(ValueError):
                stt.ChimegeSTT("test-token").transcribe(audio, sr)
        post.assert_not_called()

    @patch("stt.httpx.post")
    def test_errors_do_not_leak_token_or_response(self, post):
        engine = stt.ChimegeSTT("test-secret")
        request = httpx.Request("POST", "https://example.test")
        for status in (403, 503):
            post.return_value = httpx.Response(status, text="test-secret", request=request)
            with self.assertRaisesRegex(RuntimeError, f"^Chimege STT HTTP {status}$"):
                engine.transcribe(np.ones(10), 16000)
        post.side_effect = httpx.ReadTimeout("test-secret")
        with self.assertRaisesRegex(RuntimeError, "^Chimege STT connection failed or timed out$"):
            engine.transcribe(np.ones(10), 16000)

    @patch.dict(os.environ, {"CHIMEGE_API_TOKEN": "test-token"})
    @patch("stt.WhisperSTT")
    def test_token_selects_chimege_without_loading_whisper(self, whisper):
        self.assertIsInstance(stt.create_mn_stt(), stt.ChimegeSTT)
        whisper.assert_not_called()

    @patch("stt.time.sleep")
    @patch("stt.httpx.get")
    @patch("stt.httpx.post")
    def test_invalid_job_and_transcript_are_rejected(self, post, get, sleep):
        request = httpx.Request("POST", "https://example.test")
        engine = stt.ChimegeSTT("test-token")
        post.return_value = httpx.Response(200, json={}, request=request)
        with self.assertRaisesRegex(RuntimeError, "invalid response"):
            engine.transcribe(np.ones(10), 16000)
        get.assert_not_called()
        post.return_value = httpx.Response(200, json={"uuid": "job"}, request=request)
        for result in ({"done": "false"}, {"done": True}, [], {"done": True, "transcription": 123}):
            get.return_value = httpx.Response(200, json=result, request=request)
            with self.assertRaisesRegex(RuntimeError, "invalid response"):
                engine.transcribe(np.ones(10), 16000)

    @patch("stt.time.monotonic", side_effect=[0, 31])
    @patch("stt.httpx.get")
    @patch("stt.httpx.post")
    def test_polling_has_deadline(self, post, get, monotonic):
        post.return_value = httpx.Response(200, json={"uuid": "job"},
                                         request=httpx.Request("POST", "https://example.test"))
        with self.assertRaisesRegex(RuntimeError, "transcription timed out"):
            stt.ChimegeSTT("test-token").transcribe(np.ones(10), 16000)
        get.assert_not_called()

    @patch.dict(os.environ, {"CHIMEGE_API_TOKEN": ""})
    @patch("stt.WhisperSTT")
    def test_no_token_keeps_whisper(self, whisper):
        self.assertIs(stt.create_mn_stt(), whisper.return_value)

    @patch("stt.WhisperSTT")
    def test_bilingual_routes_mongolian_to_chimege_and_english_to_whisper(self, whisper):
        mn = Mock(spec=stt.ChimegeSTT)
        mn.transcribe.return_value = "батболд"
        whisper.return_value.language_probs.return_value = {"mn": 0.9, "en": 0.1}
        bilingual = stt.BilingualSTT(mn)
        audio = np.ones(10, np.float32)
        self.assertEqual(bilingual.transcribe(audio, 8000), ("батболд", "mn"))
        mn.transcribe.assert_called_once_with(audio, 8000)
        bilingual.transcribe_as(audio, 8000, "en")
        whisper.return_value.transcribe.assert_called_once_with(audio, 8000, language="en")


class CallFailureTest(unittest.IsolatedAsyncioTestCase):
    async def test_failed_stt_keeps_registration_state(self):
        call = Call.__new__(Call)
        call.lead, call.account = Mock(state="name"), None
        call.m = Mock(stt_pool=None)
        call.transcribe = Mock(side_effect=RuntimeError("Chimege STT HTTP 403"))
        call.hold_while = AsyncMock()
        call.play = AsyncMock()
        call.router = Mock(meta={"error": "error-clip"})
        call.router.clip.return_value = (np.zeros(10), 8000)
        await call.handle_utterance(np.ones(10))
        call.play.assert_awaited_once()
        self.assertEqual(call.lead.state, "name")


if __name__ == "__main__":
    unittest.main()
