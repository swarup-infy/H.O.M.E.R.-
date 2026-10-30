import speech_recognition as sr
import pyttsx3


def main():
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
                phrase_time_limit=8
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
