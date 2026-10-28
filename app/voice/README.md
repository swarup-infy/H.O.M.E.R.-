# Voice input (optional)

H.O.M.E.R. uses the [faster-whisper](https://github.com/SYSTRAN/faster-whisper)
library for local transcription. This is a separate, opt-in capability; it
does not change the API-based Groq chat backend.

Install from the project root:

```powershell
pip install -r requirements-voice.txt
```

Call `transcribe_file(path, language="en")` to transcribe an existing audio
file. The model is loaded lazily and defaults to `base`, CPU `int8`, and a
beam size of 1 to reduce resource use. The first use may download model files.
Set `HOMER_WHISPER_MODEL=tiny` for lower memory use or `base` for a potential
accuracy improvement. Microphone capture is intentionally not started
automatically; the desktop UI should explicitly request permission and manage
recording.
