"""Accurate speech transcription with Groq Whisper and a local CPU fallback."""
from __future__ import annotations

import logging
import os
import tempfile
from functools import lru_cache
from pathlib import Path

logger = logging.getLogger(__name__)


class VoiceDependencyError(RuntimeError):
    """Raised when optional local transcription dependencies are missing."""


def _configured_language(language: str | None) -> str | None:
    value = (language or os.getenv("HOMER_WHISPER_LANGUAGE", "auto")).strip().lower()
    return None if value in {"", "auto", "detect"} else value


def _transcribe_with_groq(audio_data: bytes, language: str | None = None) -> str | None:
    """Use Groq's multilingual Whisper API when a Groq key is configured."""
    from dotenv import load_dotenv
    load_dotenv()

    api_key = os.getenv("GROQ_API_KEY", "").strip()
    if not api_key:
        return None

    try:
        from groq import Groq
    except ImportError as exc:
        logger.warning("Groq SDK is unavailable; using local Whisper instead: %s", exc)
        return None

    model_name = os.getenv("HOMER_GROQ_STT_MODEL", "whisper-large-v3").strip()
    prompt = os.getenv(
        "HOMER_STT_PROMPT",
        "HOMER, voice assistant, desktop assistant, computer commands, "
        "Python, programming, artificial intelligence.",
    ).strip()
    kwargs = {
        "file": ("homer-microphone.wav", audio_data, "audio/wav"),
        "model": model_name,
        "response_format": "text",
        "temperature": 0.0,
    }
    detected_language = _configured_language(language)
    if detected_language:
        kwargs["language"] = detected_language
    if prompt:
        kwargs["prompt"] = prompt

    client = Groq(api_key=api_key, timeout=30.0, max_retries=1)
    result = client.audio.transcriptions.create(**kwargs)
    transcript = result if isinstance(result, str) else getattr(result, "text", "")
    return str(transcript).strip()


@lru_cache(maxsize=1)
def _load_model():
    try:
        from faster_whisper import WhisperModel
    except ImportError as exc:
        raise VoiceDependencyError(
            "Install voice dependencies with: python -m pip install -r requirements-voice.txt"
        ) from exc
    model_name = os.getenv("HOMER_WHISPER_MODEL", "base").strip() or "base"
    threads = max(1, min(8, int(os.getenv("HOMER_WHISPER_THREADS", "4"))))
    return WhisperModel(model_name, device="cpu", compute_type="int8", cpu_threads=threads)


def _transcribe_path(path: Path, language: str | None = None) -> str:
    model = _load_model()
    segments, _info = model.transcribe(
        str(path),
        language=_configured_language(language),
        beam_size=5,
        best_of=3,
        vad_filter=True,
        vad_parameters={"min_silence_duration_ms": 350, "speech_pad_ms": 350},
        condition_on_previous_text=False,
        temperature=0.0,
    )
    return " ".join(segment.text.strip() for segment in segments).strip()


def transcribe_file(file_path: str | Path, language: str | None = None) -> str:
    """Transcribe an existing audio file with CPU int8 inference."""
    path = Path(file_path).expanduser().resolve()
    if not path.is_file():
        raise FileNotFoundError(f"Audio file does not exist: {path}")
    return _transcribe_path(path, language)


def transcribe_audio_data(audio_data: bytes, language: str | None = None) -> str:
    """Prefer multilingual Groq Whisper; fall back to local CPU Whisper."""
    if not audio_data:
        raise ValueError("Audio data is empty.")

    from dotenv import load_dotenv
    load_dotenv()

    prefer_cloud = os.getenv("HOMER_STT_PROVIDER", "auto").strip().lower()
    if prefer_cloud not in {"auto", "groq", "local"}:
        raise ValueError("HOMER_STT_PROVIDER must be auto, groq, or local.")

    if prefer_cloud != "local":
        try:
            transcript = _transcribe_with_groq(audio_data, language)
            if transcript:
                return transcript
            if prefer_cloud == "groq":
                raise RuntimeError("Groq speech recognition returned an empty transcript.")
        except Exception as cloud_error:
            logger.warning("Groq speech recognition failed; trying local Whisper: %s", cloud_error)
            if prefer_cloud == "groq" and os.getenv("HOMER_STT_LOCAL_FALLBACK", "true").lower() not in {"1", "true", "yes", "on"}:
                raise RuntimeError("Groq speech recognition failed and local fallback is disabled.") from cloud_error

    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(prefix="homer-live-", suffix=".wav", delete=False) as handle:
            handle.write(audio_data)
            temporary_path = Path(handle.name)
        transcript = _transcribe_path(temporary_path, language)
        if not transcript:
            raise RuntimeError("Speech recognition returned no words. Please try speaking again.")
        return transcript
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)
