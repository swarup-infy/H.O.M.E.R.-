# H.O.M.E.R. — API-first Windows desktop assistant

H.O.M.E.R. is a small Windows assistant backend using Groq for chat and a
strict allowlist for local actions. Optional voice transcription and gesture
recognition can be installed separately.

## Architecture

- `app/main.py` — FastAPI backend
- `app/ai/groq_client.py` — hosted Groq API integration
- `app/tools/registry.py` — allowlisted local actions
- `app/voice/transcriber.py` — optional faster-whisper speech transcription
- `app/vision/gestures.py` — optional MediaPipe gesture recognition

The chat model remains hosted; no local LLM is required. Optional models are
loaded only when the corresponding feature is called.

## Quick start (Windows PowerShell)

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
Copy-Item .env.example .env
notepad .env
```

Put your Groq key in `.env`; never commit it. Start the backend:

```powershell
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Open `http://127.0.0.1:8000/docs`. Use `GET /health` or send
`POST /chat` with JSON: `{"message":"Say hello"}`.

### Screen awareness (one screenshot at a time)

Click **Ask about screen**, confirm the privacy prompt, then enter a question.
HOMER captures a single screenshot, downsizes it, and sends it to the configured
Groq vision model. The screenshot is not saved to disk by this feature. Do not
share screens containing passwords, private messages, financial data, or other
sensitive information. Set `GROQ_VISION_MODEL` in `.env` to a vision-capable
model available to your Groq account (default: `qwen/qwen3.8-27b`).

### Optional voice input

```powershell
pip install -r requirements-voice.txt
```

See [voice input docs](app/voice/README.md). First transcription may download
model weights.

### Optional hand mouse

```powershell
pip install -r requirements-vision.txt
```

Use **Export conversation** to save the current chat as a Markdown file, and **New conversation** to clear the backend's short-term context as well as the visible chat. Click **Gesture controls** in the desktop sidebar to start the webcam air mouse.
Raise your index finger to move the pointer, pinch thumb and index to click,
and raise index + middle fingers to scroll. Pause or close the window to stop
tracking. See [gesture docs](app/vision/README.md). Camera access is opt-in;
frames are processed locally and are not sent to the AI provider.

## Safety and privacy

- Bind the development server to `127.0.0.1`.
- The Groq key stays in local `.env`; `/health` never returns the key.
- Tools are allowlisted; no arbitrary shell, PowerShell, or Python execution.
- Microphone and camera access must be explicitly started by the caller.
- Hand tracking only starts after an explicit user action. Webcam frames are processed locally; closing the hand-mouse window releases the camera. Mouse actions are limited to pointer movement, click, and scroll.

## Attribution

See [docs/COMPONENTS.md](docs/COMPONENTS.md) for source projects and licensing.
