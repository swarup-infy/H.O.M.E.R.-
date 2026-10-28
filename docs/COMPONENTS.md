# H.O.M.E.R. components and upstream attribution

H.O.M.E.R. keeps its primary AI brain API-based: `app/ai/groq_client.py`
sends requests to Groq. Optional speech recognition and gesture recognition
run as separately installed modules and are not required to start FastAPI.

## Upstream projects reviewed

- **Ari VoiceCommand** — https://github.com/DO0OG/Ari-VoiceCommand
  - MIT License, copyright MAD_DOGGO. Reviewed as a Windows desktop-assistant
    architecture reference. H.O.M.E.R. does not vendor Ari's desktop code.
- **ALOS** — https://github.com/sandeepbollavaram/ALOS
  - MIT License, copyright Sandeep Kumar Bollavaram. Reviewed for its
    voice-input and modular skill concepts. H.O.M.E.R. uses its own minimal
    integration rather than copying ALOS modules with their internal
    configuration and logger dependencies.
- **faster-whisper** — https://github.com/SYSTRAN/faster-whisper
  - MIT-licensed upstream project. H.O.M.E.R. imports the installed package;
    it does not vendor the upstream source.
- **MediaPipe Samples** — https://github.com/google-ai-edge/mediapipe-samples
  - Apache License 2.0. Used as a reference for MediaPipe Tasks concepts;
    H.O.M.E.R. imports the installed MediaPipe package and does not vendor
    the upstream sample application.

Review upstream license files and model-specific terms before redistributing
any source files, assets, fonts, model files, or binaries. Model assets may
have separate terms from their software library.

## Resource-conscious defaults

- Hosted Groq model for chat: no local LLM weights are needed.
- Faster-whisper uses CPU `int8`, lazy model loading, and beam size 1.
- MediaPipe is optional and does not start the camera automatically.
- Optional components are installed separately so the basic FastAPI server
  can run without their large dependency trees.

## Current scope

This commit adds helper modules and setup documentation. It does not yet add
a desktop GUI, microphone recording endpoint, continuous webcam loop, text to
speech, or automatic gesture-to-action mapping.
