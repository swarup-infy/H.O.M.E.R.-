"""Offline model setup utility.

Run while connected to the internet:
    python -m app.ai.offline_model --download
"""
from __future__ import annotations

import argparse

from app.ai.offline_client import download_model, model_status


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare HOMER's small offline AI model.")
    parser.add_argument("--download", action="store_true", help="Download the GGUF model now.")
    parser.add_argument("--status", action="store_true", help="Show local offline model readiness.")
    args = parser.parse_args()

    if args.download:
        path = download_model()
        print(f"Offline model ready: {path}")
        return 0
    print(model_status())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
