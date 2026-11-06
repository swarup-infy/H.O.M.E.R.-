"""Lazy CPU-friendly Faster-Whisper transcription for files and live microphone audio."""
from __future__ import annotations

import os
import tempfile
from functools import lru_cache
from pathlib import Path


class VoiceDependencyError(RuntimeError):
    """Raised when optional local transcription dependencies are missing."""


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
    chosen_language = language or os.getenv("HOMER_WHISPER_LANGUAGE", "en").strip() or None
    segments, _info = model.transcribe(
        str(path), language=chosen_language, beam_size=5, best_of=5,
        vad_filter=True, vad_parameters={"min_silence_duration_ms": 400},
        condition_on_previous_text=False, temperature=0.0,
    )
    return " ".join(segment.text.strip() for segment in segments).strip()


def transcribe_file(file_path: str | Path, language: str | None = None) -> str:
    """Transcribe an existing audio file with CPU int8 inference."""
    path = Path(file_path).expanduser().resolve()
    if not path.is_file():
        raise FileNotFoundError(f"Audio file does not exist: {path}")
    return _transcribe_path(path, language)


def transcribe_audio_data(audio_data: bytes, language: str | None = None) -> str:
    """Transcribe WAV bytes captured by SpeechRecognition without cloud upload."""
    if not audio_data:
        raise ValueError("Audio data is empty.")
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(prefix="homer-live-", suffix=".wav", delete=False) as handle:
            handle.write(audio_data)
            temporary_path = Path(handle.name)
        return _transcribe_path(temporary_path, language)
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)
