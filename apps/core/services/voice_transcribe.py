"""OpenAI speech-to-text for iOS Safari customer search."""

from __future__ import annotations

import logging
import os

from django.conf import settings
from openai import (
    APIConnectionError,
    APITimeoutError,
    AuthenticationError,
    BadRequestError,
    OpenAI,
    RateLimitError,
)

logger = logging.getLogger(__name__)


class VoiceTranscribeError(Exception):
    """Transcription could not be completed."""


TRANSCRIBE_PROMPT = "請辨識台灣中文（繁體中文）客戶名稱、老闆姓名、路名、地區。"
MIN_AUDIO_BYTES = 100
VOICE_UNCLEAR_MESSAGE = "聽不清楚，請再說一次"
VOICE_QUOTA_MESSAGE = "AI 額度不足，請聯絡管理員補值。"


def _resolve_openai_api_key() -> str:
    return (
        getattr(settings, "OPENAI_API_KEY", "") or os.environ.get("OPENAI_API_KEY", "") or ""
    ).strip()


def _normalize_audio_upload(name: str, content_type: str) -> tuple[str, str]:
    """Map browser uploads (esp. iPad/iPhone Safari audio/mp4) to OpenAI-friendly metadata."""
    name = (name or "voice.webm").strip()
    ct = (content_type or "").split(";")[0].strip().lower()
    lower = name.lower()

    ios_container_types = {
        "audio/mp4",
        "audio/m4a",
        "audio/x-m4a",
        "audio/aac",
        "audio/x-caf",
        "audio/caf",
    }
    is_ios_container = (
        lower.endswith((".mp4", ".m4a", ".caf"))
        or ct in ios_container_types
        or any(token in ct for token in ("mp4", "m4a", "aac", "caf"))
    )
    if is_ios_container:
        if not lower.endswith(".m4a"):
            name = "voice.m4a"
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
            return "voice.m4a" if lower.endswith(".m4a") else name, "audio/mp4"
        if lower.endswith(".webm"):
            return name, "audio/webm"
        return "voice.webm", "audio/webm"
    return name, ct


def _log_openai_exception(
    exc: Exception,
    *,
    filename: str,
    content_type: str,
    normalized_filename: str,
    normalized_content_type: str,
    audio_file_size: int,
) -> None:
    logger.error(
        "voice_transcribe openai_error filename=%r content_type=%r "
        "normalized_filename=%r normalized_content_type=%r audio_file_size=%s "
        "exception_class=%s exception_message=%s",
        filename,
        content_type,
        normalized_filename,
        normalized_content_type,
        audio_file_size,
        exc.__class__.__name__,
        exc,
        exc_info=True,
    )


def transcribe_audio_upload(uploaded_file, *, user_agent: str = "") -> str:
    api_key = _resolve_openai_api_key()
    if not api_key:
        logger.warning("voice_transcribe missing_api_key user_agent=%r", user_agent)
        raise VoiceTranscribeError("語音服務尚未設定")

    uploaded_file.seek(0)
    raw = uploaded_file.read()
    original_name = getattr(uploaded_file, "name", None) or "voice.webm"
    original_content_type = getattr(uploaded_file, "content_type", None) or "audio/webm"
    normalized_name, normalized_content_type = _normalize_audio_upload(
        original_name,
        original_content_type,
    )
    size = len(raw)

    logger.info(
        "voice_transcribe upload filename=%r content_type=%r normalized_filename=%r "
        "normalized_content_type=%r audio_file_size=%s user_agent=%r",
        original_name,
        original_content_type,
        normalized_name,
        normalized_content_type,
        size,
        user_agent,
    )

    if not raw:
        raise VoiceTranscribeError(VOICE_UNCLEAR_MESSAGE)
    if size < MIN_AUDIO_BYTES:
        logger.warning(
            "voice_transcribe audio_too_small filename=%r audio_file_size=%s",
            original_name,
            size,
        )
        raise VoiceTranscribeError(VOICE_UNCLEAR_MESSAGE)

    client = OpenAI(api_key=api_key)
    try:
        result = client.audio.transcriptions.create(
            model="gpt-4o-mini-transcribe",
            file=(normalized_name, raw, normalized_content_type),
            language="zh",
            prompt=TRANSCRIBE_PROMPT,
        )
    except AuthenticationError as exc:
        _log_openai_exception(
            exc,
            filename=original_name,
            content_type=original_content_type,
            normalized_filename=normalized_name,
            normalized_content_type=normalized_content_type,
            audio_file_size=size,
        )
        raise VoiceTranscribeError("語音服務設定錯誤") from exc
    except RateLimitError as exc:
        _log_openai_exception(
            exc,
            filename=original_name,
            content_type=original_content_type,
            normalized_filename=normalized_name,
            normalized_content_type=normalized_content_type,
            audio_file_size=size,
        )
        raise VoiceTranscribeError(VOICE_QUOTA_MESSAGE) from exc
    except BadRequestError as exc:
        _log_openai_exception(
            exc,
            filename=original_name,
            content_type=original_content_type,
            normalized_filename=normalized_name,
            normalized_content_type=normalized_content_type,
            audio_file_size=size,
        )
        raise VoiceTranscribeError("語音格式無法辨識，請再試一次") from exc
    except (APIConnectionError, APITimeoutError) as exc:
        _log_openai_exception(
            exc,
            filename=original_name,
            content_type=original_content_type,
            normalized_filename=normalized_name,
            normalized_content_type=normalized_content_type,
            audio_file_size=size,
        )
        raise VoiceTranscribeError("語音辨識暫時無法使用") from exc
    except Exception as exc:
        _log_openai_exception(
            exc,
            filename=original_name,
            content_type=original_content_type,
            normalized_filename=normalized_name,
            normalized_content_type=normalized_content_type,
            audio_file_size=size,
        )
        raise VoiceTranscribeError("語音辨識暫時無法使用") from exc

    text = (result.text or "").strip()
    logger.info(
        "voice_transcribe ok audio_file_size=%s text_length=%s",
        size,
        len(text),
    )
    if not text:
        logger.warning(
            "voice_transcribe empty_text filename=%r content_type=%r audio_file_size=%s",
            original_name,
            original_content_type,
            size,
        )
        raise VoiceTranscribeError(VOICE_UNCLEAR_MESSAGE)
    return text
