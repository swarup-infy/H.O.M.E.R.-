# HOMER voice input and output

Install optional voice dependencies from the repository root using python -m pip install -r requirements-voice.txt.

Live microphone capture uses SpeechRecognition/PyAudio. Captured audio is converted to 16 kHz mono WAV and transcribed locally with Faster-Whisper using CPU int8 inference and beam search. The default base model balances accuracy, latency, and memory use on an 8 GB RAM computer. First use downloads model weights; allow internet for that one-time download. Set HOMER_WHISPER_MODEL=small for slower, potentially more accurate results, or tiny for lower latency. Set HOMER_WHISPER_LANGUAGE=en for English, or leave it empty for auto-detection.

If Faster-Whisper is not installed, the live UI falls back to Google's online SpeechRecognition service. Audio is not sent to Google when the local model works.

Speech output uses Windows SAPI via pyttsx3. HOMER_TTS_SPEED=1.50 is the default multiplier relative to HOMER's 165-WPM base rate (approximately 248 WPM). Allowed values are 0.75–2.00; perceived speed depends on the installed Windows voice.
