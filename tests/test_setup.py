"""Tests for HOMER's setup helper; no devices or network calls are used."""
import importlib.util
from pathlib import Path

SETUP_PATH = Path(__file__).resolve().parents[1] / "setup.py"
SPEC = importlib.util.spec_from_file_location("homer_setup", SETUP_PATH)
setup = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(setup)


def test_check_environment_reports_supported_python(monkeypatch, capsys):
    monkeypatch.setattr(setup.sys, "version_info", (3, 11, 9, "final", 0))
    monkeypatch.setattr(setup.platform, "python_version", lambda: "3.11.9")
    monkeypatch.setattr(setup.platform, "platform", lambda: "test-platform")
    monkeypatch.setattr(setup.importlib.util, "find_spec", lambda _module: object())
    monkeypatch.setattr(setup.os, "getenv", lambda *_args: "test-key")
    assert setup.check_environment() == 0
    output = capsys.readouterr().out
    assert "Supported Python version" in output
    assert "value hidden" in output
    assert "test-key" not in output
    assert "No network request" in output


def test_setup_uses_current_python_for_pip(monkeypatch):
    captured = {}
    monkeypatch.setattr("builtins.input", lambda _prompt: "yes")
    monkeypatch.setattr(setup.subprocess, "call", lambda cmd, **kwargs: captured.update(cmd=cmd, kwargs=kwargs) or 0)
    assert setup.install_core() == 0
    assert captured["cmd"][:3] == [setup.sys.executable, "-m", "pip"]
    assert captured["cmd"][-1].endswith("requirements.txt")
