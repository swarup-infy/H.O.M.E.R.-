"""Thread-safe Windows text-to-speech for HOMER.

A single dedicated thread owns the pyttsx3/SAPI engine for its entire lifetime.
Voice recognition and network calls run in Qt worker threads, so using a
persistent SAPI engine from those changing threads can make later replies silent.
"""
from __future__ import annotations

import logging
import queue
import re
import threading
from typing import Optional

import pyttsx3

logger = logging.getLogger(__name__)

VOICE_NAME = "Microsoft David Desktop"
SPEECH_RATE = 165
VOLUME = 1.0

_speech_queue: queue.Queue[Optional[str]] = queue.Queue()
_start_lock = threading.Lock()
_speech_thread: threading.Thread | None = None
_ready = threading.Event()
_start_error: BaseException | None = None


def prepare_text(text: str) -> str:
    """Remove markdown syntax and code blocks before reading the answer aloud."""
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


def _make_engine():
    """Create SAPI on the dedicated TTS thread."""
    engine = pyttsx3.init("sapi5")
    voices = engine.getProperty("voices") or []
    selected = next(
        (v for v in voices if VOICE_NAME.casefold() in v.name.casefold()),
        None,
    )
    if selected is None:
        selected = next(
            (v for v in voices if "english" in v.name.casefold()),
            None,
        )
    if selected is not None:
        engine.setProperty("voice", selected.id)
    engine.setProperty("rate", SPEECH_RATE)
    engine.setProperty("volume", VOLUME)
    return engine


def _speech_worker() -> None:
    """Own and operate the speech engine on one stable thread."""
    global _start_error
    engine = None
    try:
        engine = _make_engine()
        _ready.set()
        while True:
            text = _speech_queue.get()
            try:
                if text is None:
                    return
                engine.say(text)
                engine.runAndWait()
            except Exception:
                logger.exception("HOMER speech playback failed; rebuilding the SAPI engine.")
                try:
                    engine.stop()
                except Exception:
                    pass
                try:
                    engine = _make_engine()
                    engine.say(text)
                    engine.runAndWait()
                except Exception:
                    logger.exception("HOMER could not recover its speech engine.")
                    # Rebuild before processing the next response.
                    try:
                        engine = _make_engine()
                    except Exception:
                        logger.exception("Could not reinitialize Windows SAPI.")
                        engine = None
            finally:
                _speech_queue.task_done()
    except BaseException as exc:
        _start_error = exc
        logger.exception("HOMER text-to-speech engine failed to start.")
        _ready.set()
    finally:
        if engine is not None:
            try:
                engine.stop()
            except Exception:
                pass


def _ensure_worker() -> None:
    global _speech_thread, _start_error
    with _start_lock:
        if _speech_thread is None or not _speech_thread.is_alive():
            _start_error = None
            _ready.clear()
            _speech_thread = threading.Thread(
                target=_speech_worker,
                name="HOMER-TTS",
                daemon=True,
            )
            _speech_thread.start()
    if not _ready.wait(timeout=10):
        raise RuntimeError("HOMER's speech engine did not start within 10 seconds.")
    if _start_error is not None:
        raise RuntimeError(f"Could not start Windows text-to-speech: {_start_error}") from _start_error


def speak(text: str) -> None:
    """Queue every HOMER reply for sequential playback; wait until it has finished."""
    text = prepare_text(text)
    if not text:
        logger.warning("HOMER received an empty response for speech.")
        return
    _ensure_worker()
    # Queue.join() ensures the UI doesn't mark the assistant as listening
    # while the current answer is still speaking.
    _speech_queue.put(text)
    _speech_queue.join()


if __name__ == "__main__":
    speak("Hello! I am HOMER. This is the first response.")
    speak("This is the second response, and I should speak again.")
    speak("This is the third response, and I should still be speaking.")
