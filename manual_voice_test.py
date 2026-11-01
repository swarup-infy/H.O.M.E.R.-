"""Manual root-level voice hardware smoke test.

Run explicitly with:
    python manual_voice_test.py

This test opens a microphone and plays audio. It is intentionally excluded
from automated pytest collection.
"""
from __future__ import annotations


def main() -> None:
    try:
        import speech_recognition as sr
        import pyttsx3
    except ImportError as exc:
        raise SystemExit(
            "Voice dependencies are missing. Install them with: "
            "python -m pip install -r requirements-voice.txt"
        ) from exc

    print("Initializing HOMER voice...")
    speaker = pyttsx3.init()
    speaker.setProperty("rate", 175)

    speaker.say("Hello! I am Homer. Testing my voice system.")
    speaker.runAndWait()

    recognizer = sr.Recognizer()
    try:
        with sr.Microphone() as source:
            print("\nAdjusting microphone for background noise...")
            recognizer.adjust_for_ambient_noise(source, duration=2)

            print("Speak now...")
            audio = recognizer.listen(
                source,
                timeout=10,
                phrase_time_limit=8,
            )

        print("Recognizing speech...")
        text = recognizer.recognize_google(audio)

        print(f"\nYou said: {text}")
        speaker.say(f"You said: {text}")
        speaker.runAndWait()

    except sr.WaitTimeoutError:
        print("No speech detected. Please check your microphone.")
    except sr.UnknownValueError:
        print("I could not understand your speech.")
    except sr.RequestError as exc:
        print(f"Online recognition error: {exc}")
    except Exception as exc:
        print(f"Voice test failed: {type(exc).__name__}: {exc}")


if __name__ == "__main__":
    main()
