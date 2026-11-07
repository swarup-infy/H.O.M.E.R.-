"""Validated speech playback settings shared by HOMER voice clients."""
from __future__ import annotations

import os

from dotenv import load_dotenv

load_dotenv()

DEFAULT_BASE_RATE = 165


def speech_speed() -> float:
    """Return the requested playback multiplier, defaulting to 1.20x."""
    raw = os.getenv("HOMER_TTS_SPEED", "1.20").strip()
    try:
        value = float(raw)
    except ValueError as exc:
        raise ValueError("HOMER_TTS_SPEED must be a number between 0.75 and 2.00.") from exc
    if not 0.75 <= value <= 2.0:
        raise ValueError("HOMER_TTS_SPEED must be between 0.75 and 2.00.")
    return value


def speech_rate(base_rate: int = DEFAULT_BASE_RATE) -> int:
    """Convert a playback multiplier into pyttsx3 words-per-minute rate."""
    if not 80 <= int(base_rate) <= 300:
        raise ValueError("Base speech rate must be between 80 and 300.")
    return min(400, round(int(base_rate) * speech_speed()))
