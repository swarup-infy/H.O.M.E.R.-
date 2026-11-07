# H.O.M.E.R. components and upstream attribution

HOMER is a native Windows desktop assistant with a FastAPI backend. Groq is
the default hosted AI provider; a small optional GGUF model is used only when
the online provider cannot be reached. Voice transcription, text-to-speech,
and webcam gesture control are optional feature packs.

## Active application components

- `app/desktop.py` and `app/voice_window.py`: native PySide6 text and voice
  interfaces.
- `app/ai/groq_client.py`: online-first chat routing and local fallback.
- `app/ai/offline_client.py`: optional CPU-only GGUF fallback.
- `app/ai/vision_client.py` and `app/tools/computer_use.py`: explicit
  screen-reading and visual UI targeting.
- `app/knowledge/`: local SQLite FTS5 document and project search.
- `app/mcp_server.py` and `app/tools/`: MCP tools for browser, windows,
  audio, applications, screen and desktop context.
- `app/voice/`: optional microphone transcription and Windows speech output.
- `app/vision/mouse_control.py`: optional webcam air-mouse window.
- `app/ascii_face.py` and `app/assets/homer_core.png`: desktop assistant
  state and visual identity.

Optional dependencies are kept in separate requirements files so users do
not need to install the offline LLM, microphone stack, or webcam stack unless
they use those features. Test-only tools belong in `requirements-dev.txt`,
not the runtime requirements.

## Upstream projects reviewed

- **Ari VoiceCommand** — https://github.com/DO0OG/Ari-VoiceCommand
  - MIT License, copyright MAD_DOGGO. Reviewed as an architecture reference;
    HOMER does not vendor its desktop code.
- **ALOS** — https://github.com/sandeepbollavaram/ALOS
  - MIT License, copyright Sandeep Kumar Bollavaram. Reviewed for modular
    skills and CPU-oriented voice-input concepts; HOMER uses its own adapters.
- **faster-whisper** — https://github.com/SYSTRAN/faster-whisper
  - Installed as a dependency; its source is not vendored.
- **MediaPipe Samples** — https://github.com/google-ai-edge/mediapipe-samples
  - Apache License 2.0. Reviewed for hand-tracking concepts; sample
    applications are not vendored.
- **God's Eye View** — https://github.com/bilawalsidhu/gods-eye-view
  - HOMER can launch a separately installed local globe service. Its source
    tree is not copied into this repository. Third-party data, imagery,
    models, and feeds retain their own licenses and provider terms.

Before redistributing upstream source code, fonts, assets, model files, or
binaries, review the corresponding license. Model and asset terms may differ
from the software package license.

## Resource-conscious defaults

- Groq handles normal online chat; the optional offline model is loaded only
  when needed and uses CPU inference.
- faster-whisper loads lazily and uses CPU int8 inference.
- MediaPipe and camera access are optional and never start automatically.
- The local SQLite knowledge index avoids a heavyweight vector database.
- Keep optional dependency packs separate to reduce the default installation.

## Desktop UI automation research (reviewed, not vendored)

- **screen-use** — https://github.com/tongriyaotxt/screen-use
  - MIT-licensed Windows desktop automation with UI Automation tree matching,
    screenshot grounding, mouse/keyboard actions, and an observe-act-verify
    task loop.
- **WindowsAgent** — https://github.com/ibraheem-mustafa-dev/windowsagent
  - Reviewed as an example of UI Automation-first targeting with a vision
    fallback.
- **pywinauto** — https://github.com/pywinauto/pywinauto
  - BSD-3-Clause Python library used for Windows UI Automation and native
    window/control access.

These projects were researched as implementation references. Their code is
not copied into HOMER. Screen automation prefers accessible UI Automation
controls and uses visual targeting only when needed. Sensitive actions remain
blocked or require manual user completion.
