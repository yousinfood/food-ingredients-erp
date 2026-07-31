from io import BytesIO
from unittest.mock import MagicMock, patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings


class VoiceTranscribeApiTests(TestCase):
    def setUp(self):
        self.client = Client()

    def test_missing_audio_returns_400(self):
        response = self.client.post("/api/voice/transcribe/")
        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.json()["ok"])

    @override_settings(OPENAI_API_KEY="")
    def test_missing_api_key_returns_400(self):
        audio = SimpleUploadedFile("voice.webm", b"fake", content_type="audio/webm")
        response = self.client.post("/api/voice/transcribe/", {"audio": audio})
        self.assertEqual(response.status_code, 400)
        self.assertIn("語音服務尚未設定", response.json()["error"])

    @override_settings(OPENAI_API_KEY="test-key")
    @patch("apps.core.services.voice_transcribe.OpenAI")
    def test_success_returns_text(self, mock_openai_cls):
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client
        mock_client.audio.transcriptions.create.return_value = MagicMock(text="華都小籠包")

        audio = SimpleUploadedFile("voice.webm", b"x" * 1200, content_type="audio/webm")
        response = self.client.post("/api/voice/transcribe/", {"audio": audio})

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["ok"])
        self.assertEqual(data["text"], "華都小籠包")
        mock_client.audio.transcriptions.create.assert_called_once()
        call_kwargs = mock_client.audio.transcriptions.create.call_args.kwargs
        self.assertEqual(call_kwargs["model"], "gpt-4o-mini-transcribe")
        self.assertEqual(call_kwargs["language"], "zh")
        self.assertEqual(
            call_kwargs["prompt"],
            "請辨識台灣中文（繁體中文）客戶名稱、老闆姓名、路名、地區。",
        )

    @override_settings(OPENAI_API_KEY="test-key")
    @patch("apps.core.services.voice_transcribe.OpenAI")
    def test_empty_transcription_returns_unclear(self, mock_openai_cls):
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client
        mock_client.audio.transcriptions.create.return_value = MagicMock(text="")

        audio = SimpleUploadedFile("voice.m4a", b"x" * 1200, content_type="audio/mp4")
        response = self.client.post("/api/voice/transcribe/", {"audio": audio})

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertFalse(data["ok"])
        self.assertEqual(data["text"], "")
        self.assertIn("聽不清楚", data["error"])

    @override_settings(OPENAI_API_KEY="test-key")
    @patch("apps.core.services.voice_transcribe.OpenAI")
    def test_ipad_mp4_upload_normalizes_content_type(self, mock_openai_cls):
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client
        mock_client.audio.transcriptions.create.return_value = MagicMock(text="一中街紅豆餅")

        audio = SimpleUploadedFile("voice.mp4", b"x" * 1200, content_type="audio/mp4")
        response = self.client.post("/api/voice/transcribe/", {"audio": audio})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["text"], "一中街紅豆餅")
        call_kwargs = mock_client.audio.transcriptions.create.call_args.kwargs
        file_tuple = call_kwargs["file"]
        self.assertEqual(file_tuple[0], "voice.mp4")
        self.assertEqual(file_tuple[2], "audio/mp4")
