"""Safe local lifecycle helpers for the optional God's Eye View app.

The globe remains a separate upstream JavaScript application. HOMER only starts
its local development server and opens its loopback URL; it does not proxy,
scrape, or expose the service to the network.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from pathlib import Path
from urllib.parse import urlsplit

import httpx
from dotenv import load_dotenv

DEFAULT_GLOBE_URL = "http://127.0.0.1:4173"
_ALLOWED_HOSTS = {"127.0.0.1", "localhost", "::1"}


def get_globe_url(environ: dict[str, str] | None = None) -> str:
    """Return a validated loopback-only globe URL."""
    load_dotenv()
    env = os.environ if environ is None else environ
    raw_url = env.get("HOMER_GLOBE_URL", DEFAULT_GLOBE_URL).strip()
    try:
        parsed = urlsplit(raw_url)
        port = parsed.port
    except ValueError as exc:
        raise ValueError("HOMER_GLOBE_URL has an invalid port or URL.") from exc

    if (
        parsed.scheme != "http"
        or not parsed.hostname
        or parsed.hostname.lower() not in _ALLOWED_HOSTS
        or parsed.username is not None
        or parsed.password is not None
        or parsed.fragment
    ):
        raise ValueError(
            "HOMER_GLOBE_URL must be an HTTP localhost URL "
            "(127.0.0.1, localhost, or ::1)."
        )
    if port is not None and not 1 <= port <= 65535:
        raise ValueError("HOMER_GLOBE_URL port must be between 1 and 65535.")
    return raw_url.rstrip("/")


def get_globe_port(url: str) -> int:
    """Get the explicit URL port or its HTTP(S) default."""
    parsed = urlsplit(url)
    return parsed.port or 4173


def resolve_globe_project(
    environ: dict[str, str] | None = None,
    repo_root: Path | None = None,
) -> Path:
    """Find the separately cloned upstream project and validate its scripts."""
    load_dotenv()
    env = os.environ if environ is None else environ
    configured = env.get("HOMER_GLOBE_DIR", "").strip()
    if configured:
        project_dir = Path(configured).expanduser().resolve()
    else:
        root = repo_root or Path(__file__).resolve().parents[1]
        project_dir = (root.parent / "gods-eye-view").resolve()

    package_file = project_dir / "package.json"
    if not package_file.is_file():
        raise FileNotFoundError(
            "God's Eye View is not installed. Clone it beside HOMER with:\n"
            "  cd D:\\Software\n"
            "  git clone https://github.com/bilawalsidhu/gods-eye-view.git\n"
            "  cd gods-eye-view; npm ci\n"
            "Or set HOMER_GLOBE_DIR in .env to its folder."
        )

    try:
        package = json.loads(package_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError("God's Eye View package.json is unreadable or invalid.") from exc

    if not isinstance(package, dict) or not isinstance(package.get("scripts"), dict):
        raise RuntimeError("God's Eye View package.json has no valid scripts section.")
    if not package["scripts"].get("dev"):
        raise RuntimeError("God's Eye View package.json does not define a dev script.")
    if not (project_dir / "node_modules").is_dir():
        raise RuntimeError(
            "God's Eye View dependencies are not installed. Open its folder and run: npm ci"
        )
    return project_dir


def node_version_supported(version_text: str) -> bool:
    """Match upstream's supported Node engine range: >=24.14 <25 or >=26 <27."""
    match = re.search(r"v?(\d+)\.(\d+)\.(\d+)", version_text.strip())
    if not match:
        return False
    major, minor, _patch = map(int, match.groups())
    return (major == 24 and minor >= 14) or major == 26


def check_globe_ready(url: str, timeout: float = 1.0) -> bool:
    """Check whether the local globe HTTP server responds successfully."""
    try:
        response = httpx.get(url, timeout=timeout, follow_redirects=False)
        return 200 <= response.status_code < 400
    except httpx.HTTPError:
        return False


def start_globe_service(
    project_dir: Path,
    port: int,
    *,
    which=None,
    run=None,
    popen=None,
    windows: bool | None = None,
):
    """Start the upstream Vite server on loopback without opening a shell."""
    import os
    which = which or shutil.which
    run = run or subprocess.run
    popen = popen or subprocess.Popen

    is_windows = os.name == "nt" if windows is None else windows
    npm = (which("npm.cmd") or which("npm")) if is_windows else which("npm")
    node = which("node")
    if not npm or not node:
        raise RuntimeError("Node.js and npm are required. Install the supported Node 24.x release.")
    version = run(
        [node, "--version"], capture_output=True, text=True, timeout=5, check=False
    )
    if version.returncode != 0 or not node_version_supported(version.stdout):
        raise RuntimeError(
            "God's Eye View requires Node >=24.14 <25 or >=26 <27. "
            f"Detected: {(version.stdout or version.stderr).strip() or 'unknown'}."
        )

    if not 1 <= int(port) <= 65535:
        raise ValueError("The globe server port must be between 1 and 65535.")

    if is_windows:
        npm_cli = Path(npm).resolve().parent / "node_modules" / "npm" / "bin" / "npm-cli.js"
        if not npm_cli.is_file():
            raise RuntimeError(
                "Could not locate npm-cli.js beside npm.cmd. Repair the Node.js/npm installation."
            )
        command_prefix = [node, str(npm_cli)]
    else:
        command_prefix = [npm]

    command = command_prefix + [
        "run", "dev", "--", "--host", "127.0.0.1",
        "--port", str(int(port)), "--strictPort",
    ]
    env = os.environ.copy()
    env["BROWSER"] = "none"
    kwargs = {
        "cwd": str(Path(project_dir)),
        "env": env,
        "stdin": subprocess.DEVNULL,
        "stdout": None,
        "stderr": subprocess.STDOUT,
        "shell": False,
    }
    if is_windows:
        kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)

    log_path = Path(project_dir) / ".homer-globe.log"
    with log_path.open("ab") as log_file:
        kwargs["stdout"] = log_file
        return popen(command, **kwargs)
