# Voice assistant (optional)

HOMER includes a native voice-assistant window in `app/voice_window.py`.
Voice support is installed separately from the core desktop application.

## Install voice dependencies

From the repository root, with the HOMER virtual environment active:

```powershell
python -m pip install -r requirements-voice.txt
```

The current live microphone flow uses SpeechRecognition with Google's online
speech-recognition service. It requires a working microphone and an internet
connection. Speech output uses `pyttsx3` and the Windows speech engine.

## Start and control voice mode

Launch HOMER normally with the API running. Open the **Voice assistant**
window from the desktop sidebar. Microphone capture does not start merely
because the window is opened. Press **LISTENING OFF** to explicitly enable
continuous listening; the control changes to **LISTENING ON**. Press it again
to stop listening.

The single-request microphone control is also available in the voice window's
voice-task implementation. The continuous-listening loop processes one utterance
at a time, sends recognized text to HOMER's local API, and can speak the reply.
The user can interrupt speech with supported spoken commands such as “stop”
and request a shorter answer, summary, or more detail.

## Local Whisper transcription

HOMER also includes an optional `faster-whisper` adapter for transcribing an
existing audio file. It is separate from the live microphone path and is not
automatically loaded.

```python
from app.voice.transcriber import transcribe_file

text = transcribe_file("recording.wav", language="en")
print(text)
```

Model loading is lazy. Defaults are CPU `int8`, beam size 1, and model
`base`. The first use may download model weights. Set
`HOMER_WHISPER_MODEL=tiny` for a smaller model or `base` for a potential
accuracy improvement, and optionally `HOMER_WHISPER_THREADS=2` to limit CPU
threads.

## Privacy and safety

- Continuous microphone listening is disabled until the user presses its
  explicit control.
- Live speech recognition sends recorded audio to Google's online service.
  Do not use it for private conversations unless you are comfortable with
  that processing.
- The optional faster-whisper file transcription runs locally after model
  installation; model weights may be downloaded on first use.
- Closing the voice window asks its worker to stop. If a recognition request
  is already in progress, shutdown may take until that request returns.
