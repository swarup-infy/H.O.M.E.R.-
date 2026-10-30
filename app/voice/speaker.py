"""Reliable local text-to-speech for HOMER on Windows.

The engine is reused between replies so repeated questions do not silently
lose speech after the first response.
"""
import logging
import re
import threading

import pyttsx3

logger = logging.getLogger(__name__)

VOICE_NAME = "Microsoft David Desktop"
SPEECH_RATE = 165
VOLUME = 1.0

_speech_lock = threading.RLock()
_engine = None


def prepare_text(text: str) -> str:
    """Convert Markdown-heavy answers into readable spoken text."""
    text = re.sub(r"```[\s\S]*?```", " ", text)
    text = re.sub(r"`([^`]*)`", r"\1", text)
    text = re.sub(r"\*\*(.*?)\*\*", r"\1", text)
    text = re.sub(r"(?m)^\s{0,3}#{1,6}\s+", "", text)
    text = re.sub(r"(?m)^\s*[-*+]\s+", "", text)
    text = re.sub(r"(?m)^\s*\d+[.)]\s+", "", text)
    text = re.sub(r"https?://\S+", " ", text)
    text = re.sub(r"(?m)^\s*\|.*\|\s*$", " ", text)
    text = re.sub(r"\n+", ". ", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\.{2,}", ".", text)
    text = re.sub(r"\s+([,.!?;:])", r"\1", text)
    return text.strip()


def _create_engine():
    """Initialize and configure a fresh SAPI engine."""
    engine = pyttsx3.init("sapi5")
    voices = engine.getProperty("voices") or []
    selected = next(
        (voice for voice in voices if VOICE_NAME.casefold() in voice.name.casefold()),
        None,
    )
    if selected is None:
        selected = next(
            (voice for voice in voices if "english" in voice.name.casefold()),
            None,
        )
    if selected is not None:
        engine.setProperty("voice", selected.id)
    engine.setProperty("rate", SPEECH_RATE)
    engine.setProperty("volume", VOLUME)
    return engine


def speak(text: str) -> None:
    """Speak every non-empty HOMER response; log failures instead of crashing voice mode."""
    global _engine
    text = prepare_text(text)
    if not text:
        logger.warning("HOMER received an empty response for speech.")
        return

    with _speech_lock:
        try:
            if _engine is None:
                _engine = _create_engine()
            # Queue the entire answer and run the event loop for each response.
            _engine.stop()
            _engine.say(text)
            _engine.runAndWait()
        except Exception:
            logger.exception("HOMER text-to-speech failed; retrying with a fresh engine.")
            try:
                if _engine is not None:
                    try:
                        _engine.stop()
                    except Exception:
                        pass
                _engine = _create_engine()
                _engine.say(text)
                _engine.runAndWait()
            except Exception:
                logger.exception("HOMER text-to-speech retry failed.")
                _engine = None
                raise


if __name__ == "__main__":
    speak("Hello! I am HOMER. I will speak every response aloud.")
