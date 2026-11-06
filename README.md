# HOMER — Setup & First-Run Guide

HOMER is a native Windows desktop assistant backed by a local FastAPI service and a hosted Groq API. The language model runs remotely; you do **not** need a local LLM or a GPU. Core chat, optional voice, and optional webcam gesture controls are installed separately.

## Requirements

- Windows 10/11 (the desktop shell and computer-use integrations are Windows-oriented).
- Python 3.11 or 3.12 (64-bit recommended).
- Git.
- Microphone and speakers only for voice features.
- Webcam only for gesture controls.
- A Groq API key: https://console.groq.com/keys
- Internet for hosted AI responses, package installation, and the current Google SpeechRecognition voice mode.

## 1. Clone HOMER

```powershell
git clone https://github.com/swarup-infy/H.O.M.E.R.-.git
cd H.O.M.E.R.-
```

## 2. Create an isolated Python environment

Use the Python launcher on Windows:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
```

If PowerShell blocks activation for this terminal, run:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

Alternatively, skip activation and use the virtual-environment interpreter directly: `.venv\Scripts\python.exe`.

## 3. Install core dependencies

```powershell
python -m pip install -r requirements.txt
```

The core requirements include the API, native desktop UI and supported computer-use dependencies. Optional feature packs are separate:

```powershell
# Voice assistant: microphone recognition, speech output and local Whisper transcription
python -m pip install -r requirements-voice.txt

# Webcam hand tracking / gesture mouse
python -m pip install -r requirements-vision.txt
```

Install only the optional packs you plan to use. The first local Whisper transcription may download model weights. The webcam feature requires camera permission.

## 4. Configure your Groq API key

Create your local environment file:

```powershell
Copy-Item .env.example .env
notepad .env
```

Set your key and choose a model available to your Groq account:

```dotenv
GROQ_API_KEY=your_actual_key_here
GROQ_MODEL=openai/gpt-oss-20b
GROQ_VISION_MODEL=qwen/qwen3.8-27b
```

Never commit `.env`, paste keys into screenshots, or share them in issues. The `.env.example` file is safe to commit because it contains placeholders only.

## 5. Validate the installation

Run the built-in setup diagnostic:

```powershell
python setup.py --check
```

Run automated tests:

```powershell
python -m pytest -q
```

The diagnostic checks Python version, required imports, environment configuration and optional feature availability. It does not call Groq or access your microphone or camera.

## 6. Start HOMER

Start the API in the first PowerShell window:

```powershell
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

In a second PowerShell window, from the repository root with the same virtual environment active, launch the native desktop app:

```powershell
python -m app.desktop
```

You can also open the API documentation at http://127.0.0.1:8000/docs and check http://127.0.0.1:8000/health. Keep the API bound to `127.0.0.1`; do not expose the development server to your network.

## 7. Local RAG knowledge base

HOMER indexes supported project files and the local documents folder when the API starts. The default document folder is under the user's profile at .homer/knowledge/documents. Copy PDFs, DOCX, TXT, Markdown, CSV, or source files into that folder. Refresh with POST /knowledge/index; inspect using GET /knowledge/status and test retrieval using GET /knowledge/search?q=your-question. The local SQLite FTS5 index stays on this computer; only relevant excerpts are sent to Groq. This is a lightweight lexical retrieval pipeline, not a neural embedding/vector database.

## 8. HOMER computer control and MCP

HOMER exposes a local Model Context Protocol (MCP) server through the same FastAPI process at `http://127.0.0.1:8000/mcp/`. It uses the official Python MCP SDK v2 with Streamable HTTP. The endpoint is intended for local desktop clients only; keep the API bound to 127.0.0.1.

MCP tools include:
- Screen metadata inspection and explicit one-shot visual screen reading.
- Visible window listing, focusing, maximizing, normal closing, and launching known apps or an exact installed Start Menu shortcut by display name.
- A dedicated, visible Chromium browser with tab management, page text snapshots, safe text clicks, typing, keyboard shortcuts, and HTML media play/pause/stop/volume/seek controls.
- Normal close requests for supported application windows.

For VS Code, use [the MCP HTTP configuration example](docs/mcp-config-vscode.json). For Claude Desktop, copy [the stdio configuration example](docs/mcp-config-claude-desktop.example.json) and adjust its local HOMER folder path. To connect another compatible MCP client, configure a Streamable HTTP server with URL `http://127.0.0.1:8000/mcp/`. For a local stdio client instead, run `python -m app.mcp_server`. Do not run both transports against different copies if you expect the same browser session; the HTTP endpoint shares HOMER's FastAPI process.

### Browser setup and privacy

Run `python -m playwright install chromium` once after installing requirements. HOMER opens its own visible Chromium profile under `%USERPROFILE%\\.homer\\browser-profile`; it does not attach to or extract cookies from the user's regular Chrome/Edge profile. Supported site domains are explicitly allowlisted in `app/tools/browser_control.py`. A site must permit playback and expose an HTML audio/video element for direct media controls to work. Log in manually in the visible HOMER browser if a site requires an account.

HOMER never accepts arbitrary shell commands, arbitrary JavaScript, browser-cookie export, or automated payment/account-deletion clicks. Screen reading requires an explicit user request and sends one screenshot to the configured Groq vision model. Screen content and webpage text are untrusted data.

## 9. Optional voice and gesture features

- **Voice assistant:** install requirements-voice.txt, then open Voice assistant from the HOMER desktop sidebar. Live microphone audio is transcribed locally with Faster-Whisper (CPU int8, default base model); Google recognition remains a compatibility fallback if Faster-Whisper is not installed. The first local model use downloads model weights. Set HOMER_WHISPER_MODEL=small for slower, potentially more accurate transcription, or keep base for a lighter 8 GB RAM setup. Spoken responses default to 1.50x speed; adjust HOMER_TTS_SPEED between 0.75 and 2.00.
- **Gesture controls:** install `requirements-vision.txt`, then choose **Gesture controls**. Camera access starts only after you open the feature. Close its window to release the camera.
- **Screen awareness:** choose **Ask about screen** and confirm before sharing the screenshot with your configured hosted vision model. Do not share screens containing passwords or sensitive information.

### Wake word status

A hands-free wake phrase such as “Hey HOMER” is not currently included in the shipped voice flow. It is intentionally not simulated as a feature. A future wake-word engine should be optional, locally processed, visibly enabled, and disabled by default. Continuous listening must never start invisibly.

## Troubleshooting

| Problem | What to do |
|---|---|
| `py -3.11` is not found | Install Python 3.11 or 3.12 (enable the Python Launcher), reopen PowerShell and verify with `py --list`. |
| Activation is blocked | Use the process-scoped execution-policy command above, or invoke `.venv\Scripts\python.exe` directly. |
| `GROQ_API_KEY` missing | Check that `.env` is in the repository root and contains a valid key. |
| Model/provider error (HTTP 502) | Check the API terminal, model availability in your Groq account, and internet connection. |
| Port 8000 is occupied | Stop the other HOMER server, or choose a different port and update `HOMER_API_URL` where supported. |
| Voice packages fail on Windows | Confirm the active environment is 64-bit Python 3.11/3.12, then install the voice pack separately. |
| Camera unavailable | Close other camera applications and check Windows camera permissions. |

## Quick start

```powershell
git clone https://github.com/swarup-infy/H.O.M.E.R.-.git
cd H.O.M.E.R.-
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
Copy-Item .env.example .env
# Add GROQ_API_KEY to .env
python setup.py --check
# Terminal 1:
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
# Terminal 2:
python -m app.desktop
```

## Video walkthrough

The Mark LIII video channel can be used as general inspiration for assistant workflows, but its setup commands and Gemini key instructions are not HOMER setup instructions: https://www.youtube.com/@FatihMakes

Run the interactive microphone/speaker smoke test after installing the voice pack with `python -m app.voice.manual_voice_test` (root-level alternative: `python manual_voice_test.py`). This manually opens the microphone and plays audio; it is not part of automated CI. See also [voice docs](app/voice/README.md), [gesture docs](app/vision/README.md), and [component attribution](docs/COMPONENTS.md).
