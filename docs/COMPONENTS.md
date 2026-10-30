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
