"""Backward-compatible root entry point for the voice hardware smoke test.

Run with:
    python manual_voice_test.py

The implementation lives in app.voice.manual_voice_test so there is only one
copy of the interactive microphone and speaker check.
"""
from app.voice.manual_voice_test import main


if __name__ == "__main__":
    main()
