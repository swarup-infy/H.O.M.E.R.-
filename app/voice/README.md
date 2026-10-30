# Voice input (optional)

H.O.M.E.R. uses the [faster-whisper](https://github.com/SYSTRAN/faster-whisper)
package for local speech-to-text. It does not alter the API-based Groq chat
backend and is not loaded unless its functions are called.

Install from the repository root:

```powershell
pip install -r requirements-voice.txt
```

Use `transcribe_file(path, language="en")` with an existing supported audio
file. Model loading is lazy. Defaults are CPU `int8`, beam size 1, and model
`base`. The first use may download model weights. Set
`HOMER_WHISPER_MODEL=tiny` for a smaller model or `base` for a potential
accuracy improvement, and optionally `HOMER_WHISPER_THREADS=2` to limit CPU
threads. Microphone capture remains the responsibility of a future UI layer.
