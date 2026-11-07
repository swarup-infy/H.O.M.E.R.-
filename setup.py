"""HOMER setup helper and non-invasive environment diagnostic.

Usage:
    python setup.py          # install core requirements interactively
    python setup.py --check  # inspect environment without installing or using devices
"""
from __future__ import annotations

import argparse
import importlib.util
import os
import platform
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CORE_IMPORTS = {
    "fastapi": "fastapi",
    "uvicorn": "uvicorn",
    "groq": "groq",
    "dotenv": "python-dotenv",
    "httpx": "httpx",
    "PySide6": "PySide6",
    "pywinauto": "pywinauto",
    "psutil": "psutil",
    "pyautogui": "pyautogui",
    "PIL": "Pillow",
    "pypdf": "pypdf",
    "docx": "python-docx",
    "mcp": "mcp",
    "playwright": "playwright",
}
OPTIONAL_IMPORTS = {
    "voice": {
        "speech_recognition": "SpeechRecognition",
        "pyaudio": "PyAudio",
        "pyttsx3": "pyttsx3",
        "faster_whisper": "faster-whisper",
    },
    "vision": {
        "mediapipe": "mediapipe",
        "cv2": "opencv-python",
    },
}


def check_environment() -> int:
    """Print setup status without importing GUI/device drivers or making network calls."""
    print("HOMER setup diagnostic")
    print("=" * 28)
    print(f"Python: {platform.python_version()} ({sys.executable})")
    print(f"Platform: {platform.platform()}")
    print()

    failures = 0
    version = sys.version_info
    if not ((3, 11) <= version[:2] <= (3, 12)):
        print("[FAIL] HOMER supports Python 3.11 or 3.12.")
        failures += 1
    else:
        print("[ OK ] Supported Python version")

    print("\nCore packages:")
    for module, package in CORE_IMPORTS.items():
        installed = importlib.util.find_spec(module) is not None
        print(f"[{' OK ' if installed else 'MISS'}] {package}")
        if not installed:
            failures += 1

    print("\nOptional features:")
    for feature, modules in OPTIONAL_IMPORTS.items():
        missing = [package for module, package in modules.items()
                   if importlib.util.find_spec(module) is None]
        if missing:
            print(f"[INFO] {feature}: not fully installed ({', '.join(missing)})")
        else:
            print(f"[ OK ] {feature}: dependencies detected")

    env_file = ROOT / ".env"
    env_key = os.getenv("GROQ_API_KEY", "")
    if env_file.is_file():
        try:
            from dotenv import dotenv_values
            env_key = env_key or dotenv_values(env_file).get("GROQ_API_KEY", "")
        except Exception:
            pass
    if env_key and env_key.strip() and env_key.strip() != "replace_me":
        print("[ OK ] GROQ_API_KEY is configured (value hidden)")
    else:
        print("[WARN] GROQ_API_KEY is not configured. Add it to .env before chatting.")

    print("\nNo network request, microphone capture, or camera access was performed.")
    return 1 if failures else 0


def install_core() -> int:
    """Install only the repository's required core dependencies."""
    answer = input("Install HOMER core dependencies from requirements.txt? [y/N] ").strip().lower()
    if answer not in {"y", "yes"}:
        print("Installation cancelled.")
        return 0
    command = [sys.executable, "-m", "pip", "install", "-r", str(ROOT / "requirements.txt")]
    return subprocess.call(command, cwd=ROOT)


def main() -> int:
    parser = argparse.ArgumentParser(description="Install or diagnose the HOMER environment.")
    parser.add_argument("--check", action="store_true", help="run diagnostics; do not install packages")
    args = parser.parse_args()
    return check_environment() if args.check else install_core()


if __name__ == "__main__":
    raise SystemExit(main())
