"""Tests for the local God's Eye View service integration."""
import json

import httpx
import pytest

from app import globe_service


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1:4173",
        "http://localhost:4173",
        "http://[::1]:4173",
        "https://localhost:8443/globe",
    ],
)
def test_get_globe_url_accepts_loopback(url):
    assert globe_service.get_globe_url({"HOMER_GLOBE_URL": url}) == url


@pytest.mark.parametrize(
    "url",
    [
        "https://example.com",
        "file:///tmp/globe",
        "http://127.0.0.1:99999",
        "http://user:pass@localhost:4173",
        "http://localhost:4173/#unsafe",
    ],
)
def test_get_globe_url_rejects_non_loopback_or_malformed_url(url):
    with pytest.raises(ValueError):
        globe_service.get_globe_url({"HOMER_GLOBE_URL": url})


def test_get_globe_url_defaults_to_localhost():
    assert globe_service.get_globe_url({}) == globe_service.DEFAULT_GLOBE_URL


def test_get_globe_port_uses_default_and_explicit_port():
    assert globe_service.get_globe_port("http://localhost") == 4173
    assert globe_service.get_globe_port("https://localhost") == 443
    assert globe_service.get_globe_port("http://localhost:4173") == 4173


def test_resolve_globe_project_uses_sibling_directory(tmp_path):
    root = tmp_path / "HOMER"
    root.mkdir()
    project = tmp_path / "gods-eye-view"
    project.mkdir()
    (project / "node_modules").mkdir()
    (project / "package.json").write_text(
        json.dumps({"scripts": {"dev": "vite"}}), encoding="utf-8"
    )
    assert globe_service.resolve_globe_project({}, root) == project.resolve()


def test_resolve_globe_project_honours_environment_override(tmp_path):
    project = tmp_path / "custom-globe"
    project.mkdir()
    (project / "node_modules").mkdir()
    (project / "package.json").write_text(
        json.dumps({"scripts": {"dev": "vite"}}), encoding="utf-8"
    )
    assert globe_service.resolve_globe_project(
        {"HOMER_GLOBE_DIR": str(project)}, tmp_path / "HOMER"
    ) == project.resolve()


def test_resolve_globe_project_reports_missing_checkout(tmp_path):
    with pytest.raises(FileNotFoundError, match="git clone"):
        globe_service.resolve_globe_project({}, tmp_path / "HOMER")


def test_resolve_globe_project_requires_installed_dependencies(tmp_path):
    project = tmp_path / "gods-eye-view"
    project.mkdir()
    (project / "package.json").write_text(
        json.dumps({"scripts": {"dev": "vite"}}), encoding="utf-8"
    )
    with pytest.raises(RuntimeError, match="npm ci"):
        globe_service.resolve_globe_project({}, tmp_path / "HOMER")


@pytest.mark.parametrize(
    ("version", "expected"),
    [
        ("v24.14.0", True),
        ("v24.22.1", True),
        ("v24.13.9", False),
        ("v25.0.0", False),
        ("v26.0.0", True),
        ("v27.0.0", False),
        ("not-a-version", False),
    ],
)
def test_node_version_supported(version, expected):
    assert globe_service.node_version_supported(version) is expected


def test_check_globe_ready_success(monkeypatch):
    class Response:
        status_code = 200

    monkeypatch.setattr(globe_service.httpx, "get", lambda *a, **k: Response())
    assert globe_service.check_globe_ready("http://127.0.0.1:4173")


def test_check_globe_ready_connection_error(monkeypatch):
    def fail(*_args, **_kwargs):
        raise httpx.ConnectError("offline")

    monkeypatch.setattr(globe_service.httpx, "get", fail)
    assert not globe_service.check_globe_ready("http://127.0.0.1:4173")


def test_start_globe_service_uses_loopback_and_strict_port(tmp_path):
    calls = {}

    class Completed:
        returncode = 0
        stdout = "v24.22.1"
        stderr = ""

    def fake_run(command, **kwargs):
        calls["version_command"] = command
        return Completed()

    def fake_popen(command, **kwargs):
        calls["command"] = command
        calls["kwargs"] = kwargs
        return "process"

    result = globe_service.start_globe_service(
        tmp_path, 4173, which=lambda name: f"/bin/{name}",
        run=fake_run, popen=fake_popen,
    )
    assert result == "process"
    assert calls["command"] == [
        "/bin/npm", "run", "dev", "--", "--host", "127.0.0.1",
        "--port", "4173", "--strictPort",
    ]
    assert calls["kwargs"]["shell"] is False
    assert calls["kwargs"]["cwd"] == str(tmp_path)
    assert calls["kwargs"]["env"]["BROWSER"] == "none"


def test_start_globe_service_rejects_unsupported_node(tmp_path):
    class Completed:
        returncode = 0
        stdout = "v25.0.0"
        stderr = ""

    with pytest.raises(RuntimeError, match="requires Node"):
        globe_service.start_globe_service(
            tmp_path, 4173,
            which=lambda name: f"/bin/{name}",
            run=lambda *a, **k: Completed(),
            popen=lambda *a, **k: pytest.fail("server must not start"),
        )


def test_start_globe_service_rejects_missing_npm(tmp_path):
    with pytest.raises(RuntimeError, match="Node.js and npm"):
        globe_service.start_globe_service(
            tmp_path, 4173, which=lambda name: None
        )
