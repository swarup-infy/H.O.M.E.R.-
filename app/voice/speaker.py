"""Lightweight local text-to-speech for HOMER on Windows."""

import re
import threading

import pyttsx3


VOICE_NAME = "Microsoft David Desktop"
SPEECH_RATE = 165
VOLUME = 1.0

_speech_lock = threading.Lock()


def prepare_text(text: str) -> str:
    """Clean Markdown and prepare text for natural speech."""
    text = re.sub(r"```.*?```", " ", text, flags=re.DOTALL)
    text = re.sub(r"`([^`]*)`", r"\1", text)
    text = re.sub(r"\*\*(.*?)\*\*", r"\1", text)
    text = re.sub(r"(?m)^\s{0,3}#{1,6}\s+", "", text)
    text = re.sub(r"(?m)^\s*[-*+]\s+", "", text)
    text = re.sub(r"(?m)^\s*\d+[.)]\s+", "", text)
    text = re.sub(r"https?://\S+", "link", text)
    text = re.sub(r"\n+", ". ", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\.{2,}", ".", text)

    return text.strip()


def speak(text: str) -> None:
    """Speak text using the installed Microsoft David voice."""
    text = prepare_text(text)

    if not text:
        return

    with _speech_lock:
        engine = pyttsx3.init()

        try:
            voices = engine.getProperty("voices")

            david = next(
                (
                    voice
                    for voice in voices
                    if VOICE_NAME.lower() in voice.name.lower()
                ),
                None,
            )

            if david:
                engine.setProperty("voice", david.id)

            engine.setProperty("rate", SPEECH_RATE)
            engine.setProperty("volume", VOLUME)

            sentences = re.split(r"(?<=[.!?])\s+", text)

            for sentence in sentences:
                if sentence.strip():
                    engine.say(sentence.strip())

            engine.runAndWait()

        finally:
            engine.stop()


if __name__ == "__main__":
    speak(
        "Hello! I am HOMER, your personal AI assistant. "
        "I am ready to help you. "
        "Tell me what you would like to do today."
    )