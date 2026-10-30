# H.O.M.E.R. components and upstream attribution

H.O.M.E.R. keeps its AI brain API-based: `app/ai/groq_client.py` sends
requests to Groq. Speech transcription and gesture recognition are optional,
separately installed components.

## Upstream projects reviewed

- **Ari VoiceCommand** — https://github.com/DO0OG/Ari-VoiceCommand
  - MIT License, copyright MAD_DOGGO. Reviewed as a Windows desktop assistant
    architecture reference. H.O.M.E.R. does not vendor Ari's desktop code.
- **ALOS** — https://github.com/sandeepbollavaram/ALOS
  - MIT License, copyright Sandeep Kumar Bollavaram. Reviewed for modular
    skills and CPU-oriented voice-input concepts. H.O.M.E.R. implements
    small, self-contained adapters rather than copying ALOS modules with
    their internal config/logger dependencies.
- **faster-whisper** — https://github.com/SYSTRAN/faster-whisper
  - H.O.M.E.R. imports the installed package and does not vendor its source.
- **MediaPipe Samples** — https://github.com/google-ai-edge/mediapipe-samples
  - Apache License 2.0. Reviewed for MediaPipe Tasks concepts. H.O.M.E.R.
    imports the installed MediaPipe package, not the sample applications.

Before redistributing upstream source code, fonts, assets, model files, or
binaries, review the corresponding license. Models and assets can have terms
that differ from the software package itself.


- **God's Eye View** — https://github.com/bilawalsidhu/gods-eye-view
  - MIT-licensed application source, reviewed as a geospatial visualization
    reference. HOMER launches a separately installed local instance rather
    than vendoring its large Cesium application. Third-party data, imagery,
    models, and feeds retain their own licenses and provider terms.

## Resource-conscious defaults

- Hosted Groq API for chat; no local LLM weights are required.
- faster-whisper loads lazily and uses CPU `int8`, beam size 1.
- MediaPipe is optional and never automatically starts a camera.
- Optional dependency files keep the base API installation smaller.

## Current scope

This branch adds optional helper modules and docs. It does not yet provide a
desktop GUI, microphone recording endpoint, TTS, continuous webcam loop, or
automatic gesture-to-action mapping.


## Desktop UI automation research (reviewed, not vendored)

- **screen-use** — https://github.com/tongriyaotxt/screen-use
  - MIT-licensed Windows desktop automation with UI Automation tree matching, screenshot grounding, mouse/keyboard actions, and an observe-act-verify task loop. This is the closest architectural match for HOMER's goal of finding a visible Play button and clicking it. It can operate without a vision model for many accessible controls.
- **WindowsAgent** — https://github.com/ibraheem-mustafa-dev/windowsagent
  - MIT-licensed Windows UI Automation-first agent with a vision fallback. Useful for targeting named controls more reliably than guessed screen coordinates.
- **pywinauto** — https://github.com/pywinauto/pywinauto
  - BSD-3-Clause Python library for Windows UI Automation and native window/control access. A lighter building block for application-specific automation.

These projects were researched as implementation references. Their code is not copied into HOMER by this commit. A robust screen agent should prefer UI Automation/accessibility names, use visual coordinate grounding only when needed, and verify the screen after every action. Full-screen access is powerful, so the user should remain able to approve sensitive actions and stop automation immediately.
