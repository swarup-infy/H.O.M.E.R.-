"""Record microphone audio to a temporary WAV file for HOMER."""

from __future__ import annotations

import tempfile
import wave
from pathlib import Path

import sounddevice as sd


SAMPLE_RATE = 16000
CHANNELS = 1
DEFAULT_DURATION = 5
DEFAULT_DEVICE = 1


def record_audio(
    duration: int = DEFAULT_DURATION,
    device: int | None = DEFAULT_DEVICE,
) -> Path:
    """Record audio and return the path to the resulting WAV file."""
    if duration < 1 or duration > 60:
        raise ValueError("Recording duration must be between 1 and 60 seconds.")

    if device is not None:
        devices = sd.query_devices()
        if device < 0 or device >= len(devices):
            raise ValueError(f"Invalid microphone device index: {device}")

        if devices[device]["max_input_channels"] < 1:
            raise ValueError(f"Device {device} is not an input device.")

    print(f"Recording for {duration} seconds. Speak now!")

    audio = sd.rec(
        int(duration * SAMPLE_RATE),
        samplerate=SAMPLE_RATE,
        channels=CHANNELS,
        dtype="int16",
        device=device,
    )
    sd.wait()

    with tempfile.NamedTemporaryFile(
        suffix=".wav",
        prefix="homer_recording_",
        delete=False,
    ) as temporary_file:
        audio_path = Path(temporary_file.name)

    try:
        with wave.open(str(audio_path), "wb") as wav_file:
            wav_file.setnchannels(CHANNELS)
            wav_file.setsampwidth(2)
            wav_file.setframerate(SAMPLE_RATE)
            wav_file.writeframes(audio.tobytes())
    except Exception:
        audio_path.unlink(missing_ok=True)
        raise

    print(f"Recording saved: {audio_path}")
    return audio_path