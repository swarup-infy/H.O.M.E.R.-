"""Windows master audio controls are unit-tested with a fake endpoint."""
from app.tools import audio_control


class FakeEndpoint:
    def __init__(self):
        self.volume = 0.42
        self.muted = False

    def GetMasterVolumeLevelScalar(self):
        return self.volume

    def GetMute(self):
        return self.muted

    def SetMasterVolumeLevelScalar(self, value, _context):
        self.volume = value

    def SetMute(self, value, _context):
        self.muted = bool(value)


def test_get_system_audio_reports_volume_and_mute(monkeypatch):
    endpoint = FakeEndpoint()
    monkeypatch.setattr(audio_control, "_endpoint", lambda: endpoint)
    assert audio_control.get_system_audio() == {
        "ok": True, "volume": 42, "muted": False, "device": "default_output"
    }


def test_set_system_volume_validates_and_updates(monkeypatch):
    endpoint = FakeEndpoint()
    monkeypatch.setattr(audio_control, "_endpoint", lambda: endpoint)
    result = audio_control.control_system_audio("set", 75)
    assert result["ok"] is True
    assert result["volume"] == 75


def test_mute_and_unmute_system_audio(monkeypatch):
    endpoint = FakeEndpoint()
    monkeypatch.setattr(audio_control, "_endpoint", lambda: endpoint)
    assert audio_control.control_system_audio("mute")["muted"] is True
    assert audio_control.control_system_audio("unmute")["muted"] is False


def test_system_volume_steps_are_bounded(monkeypatch):
    endpoint = FakeEndpoint()
    endpoint.volume = 0.98
    monkeypatch.setattr(audio_control, "_endpoint", lambda: endpoint)
    assert audio_control.control_system_audio("volume_up")["volume"] == 100
    endpoint.volume = 0.02
    assert audio_control.control_system_audio("volume_down")["volume"] == 0


def test_invalid_system_audio_requests_are_rejected():
    assert audio_control.control_system_audio("launch")["ok"] is False
    assert audio_control.control_system_audio("set", 101)["ok"] is False
    assert audio_control.control_system_audio("set", True)["ok"] is False
