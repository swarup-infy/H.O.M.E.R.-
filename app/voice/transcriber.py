"""Lazy, CPU-friendly speech transcription using faster-whisper.

No model is loaded at import time. The first call to transcribe_file() loads
the configured local model, which may download weights from Hugging Face.
"""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path


class VoiceDependencyError(RuntimeError):
    """Raised when the optional transcription package is not installed."""


@lru_cache(maxsize=1)
def _load_model():
    try:
        from faster_whisper import WhisperModel
    except ImportError as exc:
        raise VoiceDependencyError(
            "Install optional voice dependencies with: "
            "pip install -r requirements-voice.txt"
        ) from exc

    model_name = os.getenv("HOMER_WHISPER_MODEL", "base")
    threads = max(1, int(os.getenv("HOMER_WHISPER_THREADS", "4")))
    return WhisperModel(
        model_name,
        device="cpu",
        compute_type="int8",
        cpu_threads=threads,
    )


def transcribe_file(file_path: str | Path, language: str | None = None) -> str:
    """Transcribe an existing audio file using CPU int8 inference."""
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
