"""OpenAI speech-to-text for iOS Safari customer search."""

from __future__ import annotations

import logging

from django.conf import settings
from openai import OpenAI

logger = logging.getLogger(__name__)


class VoiceTranscribeError(Exception):
    """Transcription could not be completed."""


TRANSCRIBE_PROMPT = "請辨識台灣中文（繁體中文）客戶名稱、老闆姓名、路名、地區。"
MIN_AUDIO_BYTES = 100
VOICE_UNCLEAR_MESSAGE = "聽不清楚，請再說一次"


def _normalize_audio_upload(name: str, content_type: str) -> tuple[str, str]:
    """Map browser uploads (esp. iPad Safari audio/mp4) to OpenAI-friendly file metadata."""
    name = (name or "voice.webm").strip()
    ct = (content_type or "").split(";")[0].strip().lower()
    lower = name.lower()

    if lower.endswith((".mp4", ".m4a", ".caf")) or "mp4" in ct or "m4a" in ct or ct in (
        "audio/aac",
        "audio/x-caf",
    ):
        if not lower.endswith((".mp4", ".m4a", ".caf")):
            name = "voice.m4a" if ("aac" in ct or "m4a" in ct) else "voice.mp4"
        return name, "audio/mp4"
    if lower.endswith(".webm") or "webm" in ct:
        if not lower.endswith(".webm"):
            name = "voice.webm"
        return name, "audio/webm"
    if lower.endswith(".wav") or "wav" in ct:
        if not lower.endswith(".wav"):
            name = "voice.wav"
        return name, "audio/wav"
    if ct in ("", "application/octet-stream"):
        if lower.endswith((".mp4", ".m4a")):
            return name, "audio/mp4"
        if lower.endswith(".webm"):
            return name, "audio/webm"
        return "voice.webm", "audio/webm"
    return name, ct


def transcribe_audio_upload(uploaded_file, *, user_agent: str = "") -> str:
    api_key = (settings.OPENAI_API_KEY or "").strip()
    if not api_key:
        raise VoiceTranscribeError("語音服務尚未設定")

    uploaded_file.seek(0)
    raw = uploaded_file.read()
    name = getattr(uploaded_file, "name", None) or "voice.webm"
    content_type = getattr(uploaded_file, "content_type", None) or "audio/webm"
    name, content_type = _normalize_audio_upload(name, content_type)
    size = len(raw)

    logger.info(
        "voice_transcribe start user_agent=%r mime_type=%r audio_file_size=%s filename=%r",
        user_agent,
        content_type,
        size,
        name,
    )

    if not raw:
        logger.warning(
            "voice_transcribe empty_upload user_agent=%r mime_type=%r audio_file_size=0",
            user_agent,
            content_type,
        )
        raise VoiceTranscribeError(VOICE_UNCLEAR_MESSAGE)
    if size < MIN_AUDIO_BYTES:
        logger.warning(
            "voice_transcribe audio_too_small user_agent=%r mime_type=%r audio_file_size=%s",
            user_agent,
            content_type,
            size,
        )
        raise VoiceTranscribeError(VOICE_UNCLEAR_MESSAGE)

    client = OpenAI(api_key=api_key)
    try:
        result = client.audio.transcriptions.create(
            model="gpt-4o-mini-transcribe",
            file=(name, raw, content_type),
            language="zh",
            prompt=TRANSCRIBE_PROMPT,
        )
    except Exception as exc:
        logger.warning(
            "voice_transcribe api_error user_agent=%r mime_type=%r audio_file_size=%s error=%s",
            user_agent,
            content_type,
            size,
            exc,
            exc_info=True,
        )
        raise VoiceTranscribeError("語音辨識暫時無法使用") from exc

    text = (result.text or "").strip()
    logger.info(
        "voice_transcribe ok user_agent=%r mime_type=%r audio_file_size=%s transcription_text=%r",
        user_agent,
        content_type,
        size,
        text,
    )
    if not text:
        logger.warning(
            "voice_transcribe empty_text user_agent=%r mime_type=%r audio_file_size=%s",
            user_agent,
            content_type,
            size,
        )
        raise VoiceTranscribeError(VOICE_UNCLEAR_MESSAGE)
    return text
