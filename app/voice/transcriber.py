"""Lazy, CPU-friendly speech transcription using faster-whisper.

This module never loads a model at import time. The first call to
transcribe_file() downloads/loads the configured model, so use a small model
and int8 compute on laptops with limited RAM.
"""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path


class VoiceDependencyError(RuntimeError):
    """Raised when optional voice dependencies are unavailable."""


@lru_cache(maxsize=1)
def _load_model():
    try:
        from faster_whisper import WhisperModel
    except ImportError as exc:
        raise VoiceDependencyError(
            "Voice transcription requires the optional dependencies. "
            "Install with: pip install -r requirements-voice.txt"
        ) from exc

    model_name = os.getenv("HOMER_WHISPER_MODEL", "base")
    # CPU int8 avoids requiring a GPU. Lower HOMER_WHISPER_MODEL to 'tiny'
    # if latency or memory use is too high.
    return WhisperModel(
        model_name,
        device="cpu",
        compute_type="int8",
        cpu_threads=max(1, int(os.getenv("HOMER_WHISPER_THREADS", "4"))),
    )


def transcribe_file(file_path: str | Path, language: str | None = None) -> str:
    """Transcribe an existing audio file to plain text.

    Args:
        file_path: Path to a supported audio file.
        language: Optional ISO language code such as 'en'.

    Returns:
        The transcript as a string.
    """
    path = Path(file_path).expanduser().resolve()
    if not path.is_file():
        raise FileNotFoundError(f"Audio file does not exist: {path}")

    model = _load_model()
    segments, _info = model.transcribe(
        str(path),
        language=language,
        beam_size=1,
        vad_filter=True,
        condition_on_previous_text=False,
    )
    return " ".join(segment.text.strip() for segment in segments).strip()
