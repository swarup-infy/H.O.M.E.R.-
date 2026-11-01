"""Voice interface for the existing HOMER API."""

import logging

import requests
import speech_recognition as sr
import pyttsx3

API_URL = "http://127.0.0.1:8000/chat"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class HomerVoiceAssistant:
    def __init__(self):
        self.recognizer = sr.Recognizer()
        self.recognizer.dynamic_energy_threshold = True
        self.recognizer.pause_threshold = 0.8

        self.speaker = pyttsx3.init()
        self.speaker.setProperty("rate", 170)

        self.running = False

    def speak(self, text: str) -> None:
        """Speak every HOMER response aloud."""
        text = text.strip()

        if not text:
            return

        print(f"\nHOMER: {text}")

        try:
            self.speaker.stop()
            self.speaker.say(text)
            self.speaker.runAndWait()
        except Exception:
            logger.exception("HOMER text-to-speech failed")
    def ask_homer(self, message: str) -> str:
        """Send recognized speech to the existing HOMER API."""
        response = requests.post(
            API_URL,
            json={"message": message},
            timeout=90,
        )
        response.raise_for_status()
        return response.json()["reply"]

    def listen_once(self) -> str | None:
        """Capture and transcribe one spoken message."""
        try:
            with sr.Microphone() as source:
                print("\nListening... Speak now.")
                audio = self.recognizer.listen(
                    source,
                    timeout=15,
                    phrase_time_limit=15,
                )

            print("Recognizing speech...")
            text = self.recognizer.recognize_google(
                audio,
                language="en-IN",
            )

            print(f"You: {text}")
            return text.strip()

        except sr.WaitTimeoutError:
            print("No speech detected.")
        except sr.UnknownValueError:
            print("I couldn't understand that. Please try again.")
        except sr.RequestError as exc:
            logger.error("Speech recognition failed: %s", exc)
        except Exception:
            logger.exception("Microphone error")

        return None

    def run(self) -> None:
        """Run the continuous voice conversation."""
        self.running = True
        self.speak(
            "Hello! I am HOMER. I am ready to help. "
            "Say stop listening to exit."
        )

        try:
            with sr.Microphone() as source:
                print("Calibrating microphone...")
                self.recognizer.adjust_for_ambient_noise(
                    source,
                    duration=1.5,
                )

            while self.running:
                text = self.listen_once()

                if not text:
                    continue

                normalized = text.lower().strip(" .!?")

                if normalized in {
                    "stop",
                    "stop listening",
                    "exit",
                    "goodbye homer",
                }:
                    self.speak("Goodbye! Talk to you later.")
                    break

                try:
                    reply = self.ask_homer(text)
                    self.speak(reply)
                except requests.RequestException:
                    logger.exception("Could not contact HOMER API")
                    self.speak(
                        "I couldn't reach my AI service. "
                        "Please check that the HOMER backend is running."
                    )

        except Exception:
            logger.exception("Voice assistant stopped unexpectedly")
        finally:
            self.running = False


if __name__ == "__main__":
    HomerVoiceAssistant().run()