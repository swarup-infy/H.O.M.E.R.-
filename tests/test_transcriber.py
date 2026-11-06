from pathlib import Path
from types import SimpleNamespace

from app.voice import transcriber


def test_transcribe_audio_data_uses_local_model_and_cleans_temp_file(monkeypatch):
    observed = {}

    class FakeModel:
        def transcribe(self, path, **kwargs):
            observed["path"] = Path(path)
            observed["kwargs"] = kwargs
            assert observed["path"].is_file()
            return iter([SimpleNamespace(text=" hello HOMER ")]), SimpleNamespace(language="en")

    monkeypatch.setattr(transcriber, "_load_model", lambda: FakeModel())
    result = transcriber.transcribe_audio_data(b"fake wav bytes", language="en")

    assert result == "hello HOMER"
    assert observed["kwargs"]["beam_size"] == 5
    assert observed["kwargs"]["vad_filter"] is True
    assert observed["kwargs"]["condition_on_previous_text"] is False
    assert not observed["path"].exists()


def test_transcribe_file_requires_existing_file(tmp_path):
    missing = tmp_path / "missing.wav"
    try:
        transcriber.transcribe_file(missing)
    except FileNotFoundError:
        pass
    else:
        raise AssertionError("A missing audio file must raise FileNotFoundError")
