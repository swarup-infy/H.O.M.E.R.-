import speech_recognition as sr
import pyttsx3


def main():
    speaker = pyttsx3.init()
    speaker.setProperty("rate", 165)

    recognizer = sr.Recognizer()
    recognizer.dynamic_energy_threshold = True
    recognizer.pause_threshold = 0.8
    recognizer.non_speaking_duration = 0.4

    try:
        with sr.Microphone() as source:
            print("Calibrating microphone...")
            recognizer.adjust_for_ambient_noise(source, duration=2)

            speaker.say("HOMER is listening. Please speak clearly.")
            speaker.runAndWait()

            print("Listening... Speak your complete sentence.")
            audio = recognizer.listen(
                source,
                timeout=15,
                phrase_time_limit=12,
            )

        print("Recognizing speech...")
        text = recognizer.recognize_google(audio, language="en-IN")

        print(f"\nYou said: {text}")
        speaker.say(text)
        speaker.runAndWait()

    except sr.WaitTimeoutError:
        print("No speech detected.")

    except sr.UnknownValueError:
        print("I couldn't understand that. Please speak a little more clearly.")

    except sr.RequestError as exc:
        print(f"Speech recognition service error: {exc}")

    except Exception as exc:
        print(f"Error: {type(exc).__name__}: {exc}")


if __name__ == "__main__":
    main()