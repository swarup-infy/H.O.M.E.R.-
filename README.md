# HOMER — Setup & First-Run Guide

HOMER is a native Windows desktop assistant backed by a local FastAPI service. Groq is the default online AI, with an optional lightweight CPU-only local model as an automatic fallback when Groq cannot be reached. Core chat, optional offline AI, voice, and webcam gesture controls are installed separately.

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

## 8. Automatic online/offline AI

HOMER always tries Groq first. If the Groq API cannot be reached, times out, or returns a temporary server error, HOMER automatically switches that request to a small local model. When Groq is reachable again, the next request uses Groq automatically. Invalid API keys and authentication/permission errors are reported instead of silently switching providers. Rate-limit responses are also reported as online-provider errors.

The offline fallback is **SmolLM2-360M-Instruct Q4_K_M** (a roughly 271 MB GGUF file), loaded through the CPU build of `llama-cpp-python`. Its conservative defaults are a 1,536-token context, two CPU threads, a 32-token batch, memory-mapped weights, and zero GPU layers. Before loading, HOMER checks that at least 900 MB of system memory is available. This is designed for low-memory 4 GB RAM / CPU-only computers, but actual performance depends on how much memory Windows and other running applications are using. It is deliberately small; expect simpler and less reliable answers than Groq. Expect simpler and less reliable answers than Groq; it is an English-focused helper, not a replacement for the online model. Offline mode does not call browser/computer tools or access cloud services. It can use HOMER's local SQLite knowledge index.

### One-time offline setup (while internet is available)

Install the optional CPU runtime and Hugging Face downloader:

```powershell
python -m pip install -r requirements-offline.txt
```

Download the model once (about 271 MB):

```powershell
python -m app.ai.offline_model --download
```

The file is stored by default in `%USERPROFILE%\\.homer\\models`. The model must be downloaded before you disconnect from the internet; the fallback never tries to download weights while offline. To check readiness and the last provider used, open `http://127.0.0.1:8000/ai/status`.

Optional settings in `.env`:

```dotenv
HOMER_OFFLINE_FALLBACK_ENABLED=true
HOMER_OFFLINE_THREADS=2
HOMER_OFFLINE_MAX_TOKENS=160
HOMER_OFFLINE_CONTEXT_TOKENS=1536
HOMER_OFFLINE_BATCH_SIZE=32
HOMER_OFFLINE_MIN_AVAILABLE_RAM_MB=900
# Optional: use a different local GGUF file
# HOMER_OFFLINE_MODEL_PATH=C:\\Models\\SmolLM2-360M-Instruct-Q4_K_M.gguf
```

Text chat and voice chat both use the same `POST /chat` backend, so the provider switch applies to both automatically. Windows text-to-speech continues to speak whichever reply the backend returns.

## 9. HOMER computer control and MCP

HOMER exposes a local Model Context Protocol (MCP) server through the same FastAPI process at `http://127.0.0.1:8000/mcp/`. It uses the official Python MCP SDK v2 with Streamable HTTP. The endpoint is intended for local desktop clients only; keep the API bound to 127.0.0.1.

MCP tools include:
- Screen metadata inspection and explicit one-shot visual screen reading.
- Visible window listing, focusing, maximizing, normal closing, and launching known apps or an exact installed Start Menu shortcut by display name.
- A dedicated, visible browser using bundled Chromium, installed Chrome, Edge, or Brave (selectable in .env), with tab management, back/forward/reload navigation, page text snapshots, safe text clicks, typing, keyboard shortcuts, and HTML media play/pause/stop/volume/seek controls.
- Windows master speaker volume and mute controls, global media play/pause/next/previous, installed Start Menu app discovery, and per-window minimize/restore/maximize/focus/close.
- Normal close requests for supported application windows.

For VS Code, use [the MCP HTTP configuration example](docs/mcp-config-vscode.json). For Claude Desktop, copy [the stdio configuration example](docs/mcp-config-claude-desktop.example.json) and adjust its local HOMER folder path. To connect another compatible MCP client, configure a Streamable HTTP server with URL `http://127.0.0.1:8000/mcp/`. For a local stdio client instead, run `python -m app.mcp_server`. Do not run both transports against different copies if you expect the same browser session; the HTTP endpoint shares HOMER's FastAPI process.

### New desktop controls

The MCP server exposes the same local tools to compatible MCP clients over stdio or Streamable HTTP. It now includes in-process tested tool discovery, a `homer://capabilities` resource, and a `desktop_voice_assistant_guide` prompt. New desktop actions include installed-app discovery, window minimize/restore, master speaker volume get/set/mute/unmute, and global media controls. System audio uses the Windows Core Audio endpoint through pycaw; these controls require Windows and the added pycaw/comtypes packages.

Check the AI provider and offline fallback at `GET /ai/status`. Check the selected browser engine without opening a window by calling the `get_browser_status` MCP tool. Use `get_desktop_context` for a compact snapshot of open windows, browser configuration, and master audio state; it does not capture a screenshot. The MCP HTTP endpoint is local-only by default. Do not expose it to a public network without authentication and a deliberate security review.

### Browser setup and privacy

Run `python -m playwright install chromium` once after installing requirements if you choose bundled Chromium. Set `HOMER_BROWSER_CHANNEL=chromium`, `chrome`, `msedge`, or `brave` to select the browser engine. HOMER creates a separate visible profile under `%USERPROFILE%\\.homer\\browser-profile-<channel>`; it does not attach to or extract cookies from your normal browser profile. For Brave in a non-standard folder, set `HOMER_BRAVE_EXECUTABLE`. Supported site domains are explicitly allowlisted in `app/tools/browser_control.py`. A site must permit playback and expose an HTML audio/video element for direct media controls to work. Log in manually in the visible HOMER browser if a site requires an account.

HOMER never accepts arbitrary shell commands, arbitrary JavaScript, browser-cookie export, automated sign-in/submission/payment/account-deletion clicks, or automatic typing into password, email, verification-code, or payment fields. Complete those sensitive steps manually. Screen reading requires an explicit user request and sends one screenshot to the configured Groq vision model. Screen content and webpage text are untrusted data.

## 10. Optional voice and gesture features

- **Voice assistant:** install requirements-voice.txt, then open Voice assistant from the HOMER desktop sidebar. Live microphone audio is transcribed locally with Faster-Whisper (CPU int8, default base model); Google recognition remains a compatibility fallback if Faster-Whisper is not installed. For fully offline voice chat, install the voice pack and run a microphone transcription once while online so Whisper downloads its model weights before you disconnect. The first local model use downloads model weights. Set HOMER_WHISPER_MODEL=small for slower, potentially more accurate transcription, or keep base for a lighter 8 GB RAM setup. Spoken responses default to 1.50x speed; adjust HOMER_TTS_SPEED between 0.75 and 2.00.
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
