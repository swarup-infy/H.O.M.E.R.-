"""Windows master-output audio controls using the Core Audio endpoint API."""
from __future__ import annotations

import platform
from typing import Any


def _endpoint():
    if platform.system() != "Windows":
        raise RuntimeError("System audio controls are supported on Windows only.")
    try:
        from ctypes import POINTER, cast
        from comtypes import CLSCTX_ALL
        from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
    except ImportError as exc:
        raise RuntimeError(
            "System audio controls require pycaw. Install the updated requirements.txt."
        ) from exc

    device = AudioUtilities.GetSpeakers()
    interface = device.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
    return cast(interface, POINTER(IAudioEndpointVolume))


def get_system_audio() -> dict[str, Any]:
    """Read the default Windows output volume and mute state."""
    try:
        endpoint = _endpoint()
        return {
            "ok": True,
            "volume": round(endpoint.GetMasterVolumeLevelScalar() * 100),
            "muted": bool(endpoint.GetMute()),
            "device": "default_output",
        }
    except Exception as exc:
        return {"ok": False, "error": "Could not read system audio (" + type(exc).__name__ + ")."}


def control_system_audio(action: str, volume: int | None = None) -> dict[str, Any]:
    """Get/set/mute/unmute Windows master output volume."""
    if not isinstance(action, str) or action not in {"get", "set", "mute", "unmute", "volume_up", "volume_down"}:
        return {"ok": False, "error": "Unsupported system audio action."}
    if action == "set" and (
        not isinstance(volume, int) or isinstance(volume, bool) or not 0 <= volume <= 100
    ):
        return {"ok": False, "error": "Volume must be an integer between 0 and 100."}
    try:
        endpoint = _endpoint()
        if action == "set":
            endpoint.SetMasterVolumeLevelScalar(volume / 100.0, None)
        elif action == "mute":
            endpoint.SetMute(1, None)
        elif action == "unmute":
            endpoint.SetMute(0, None)
        elif action == "volume_up":
            current = endpoint.GetMasterVolumeLevelScalar()
            endpoint.SetMasterVolumeLevelScalar(min(1.0, current + 0.05), None)
        elif action == "volume_down":
            current = endpoint.GetMasterVolumeLevelScalar()
            endpoint.SetMasterVolumeLevelScalar(max(0.0, current - 0.05), None)
        return get_system_audio()
    except Exception as exc:
        return {"ok": False, "error": "System audio action failed (" + type(exc).__name__ + ")."}
