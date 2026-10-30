"""Reliable Windows text-to-speech for HOMER.

Each reply gets a fresh SAPI engine. This avoids silent subsequent replies caused
by a reused pyttsx3/SAPI event loop on Windows. A single worker thread owns all
speech engines, and each queued request receives a completion/error signal.
"""
from __future__ import annotations

import logging
import queue
import re
import threading
from dataclasses import dataclass, field

import pyttsx3

logger = logging.getLogger(__name__)

VOICE_NAME = "Microsoft David Desktop"
SPEECH_RATE = 165
VOLUME = 1.0
SPEECH_TIMEOUT_SECONDS = 90.0


@dataclass
class _SpeechRequest:
    text: str
    done: threading.Event = field(default_factory=threading.Event)
    errors: list[BaseException] = field(default_factory=list)


_speech_queue: queue.Queue[_SpeechRequest | None] = queue.Queue()
_start_lock = threading.Lock()
_speech_thread: threading.Thread | None = None
_ready = threading.Event()
_start_error: BaseException | None = None
_active_engine = None
_active_engine_lock = threading.Lock()
_stop_requested = threading.Event()


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
    """Create a new SAPI engine on the dedicated speech thread."""
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


def _speech_worker() -> None:
    """Process speech requests serially; isolate each reply in a fresh engine."""
    global _start_error, _active_engine
    _ready.set()
    while True:
        request = _speech_queue.get()
        try:
            if request is None:
                return
            engine = None
            try:
                engine = _make_engine()
                with _active_engine_lock:
                    _active_engine = engine
                _stop_requested.clear()
                engine.say(request.text)
                engine.runAndWait()
            except BaseException as exc:
                request.errors.append(exc)
                logger.exception("HOMER could not play a speech response.")
            finally:
                if engine is not None:
                    try:
                        engine.stop()
                    except Exception:
                        logger.debug("Ignoring an error while stopping SAPI.", exc_info=True)
                with _active_engine_lock:
                    if _active_engine is engine:
                        _active_engine = None
        finally:
            if request is not None:
                request.done.set()
            _speech_queue.task_done()


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


def stop_speaking() -> None:
    """Immediately request cancellation of the currently spoken response."""
    _stop_requested.set()
    with _active_engine_lock:
        engine = _active_engine
    if engine is not None:
        try:
            engine.stop()
        except Exception:
            logger.exception("HOMER could not interrupt the current speech.")


def speak(text: str) -> None:
    """Speak one response and return only after playback finishes or fails."""
    text = prepare_text(text)
    if not text:
        logger.warning("HOMER received an empty response for speech.")
        return
    _ensure_worker()
    request = _SpeechRequest(text=text)
    _speech_queue.put(request)
    if not request.done.wait(timeout=SPEECH_TIMEOUT_SECONDS):
        raise RuntimeError(
            f"HOMER voice playback did not finish within {SPEECH_TIMEOUT_SECONDS:.0f} seconds."
        )
    if request.errors:
        raise RuntimeError(f"Windows text-to-speech failed: {request.errors[0]}") from request.errors[0]


if __name__ == "__main__":
    speak("Hello! I am HOMER. This is the first response.")
    speak("This is the second response, and I should speak again.")
    speak("This is the third response, and I should still be speaking.")
