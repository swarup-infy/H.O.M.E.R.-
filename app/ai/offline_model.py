"""Lazy CPU-only GGUF fallback model for HOMER.

The optional llama.cpp runtime is imported only when Groq is unavailable.
The model is never loaded during normal online operation.
"""
from __future__ import annotations

import argparse
import importlib.util
import logging
import os
import threading
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

MODEL_REPO = "Qwen/Qwen2.5-0.5B-Instruct-GGUF"
MODEL_NAME = "Qwen2.5-0.5B-Instruct (GGUF Q4_0)"
MODEL_FILENAME = "qwen2.5-0.5b-instruct-q4_0.gguf"

_model: Any | None = None
_model_lock = threading.RLock()


class OfflineModelUnavailable(RuntimeError):
    """Raised when the optional offline runtime or model file is missing."""


def model_path() -> Path:
    """Return the configured or default local GGUF model path."""
    configured = os.getenv("HOMER_OFFLINE_MODEL_PATH", "").strip()
    if configured:
        return Path(configured).expanduser()
    folder = Path.home() / ".homer" / "models"
    q4_0 = folder / MODEL_FILENAME
    q4_k_m = folder / "qwen2.5-0.5b-instruct-q4_k_m.gguf"
    return q4_0 if q4_0.is_file() or not q4_k_m.is_file() else q4_k_m


def model_status() -> dict[str, Any]:
    """Return safe model readiness information without loading the model."""
    path = model_path()
    downloaded = path.is_file() and path.stat().st_size >= 100_000_000
    runtime_installed = importlib.util.find_spec("llama_cpp") is not None
    return {
        "ready": downloaded and runtime_installed,
        "downloaded": downloaded,
        "runtime_installed": runtime_installed,
        "model": MODEL_NAME,
        "file": path.name,
        "size_mb": round(path.stat().st_size / (1024 * 1024), 1) if downloaded else None,
        "runtime": "llama.cpp CPU",
    }


def download_model() -> Path:
    """Download the small official Q4_0 GGUF model; run this while online."""
    try:
        from huggingface_hub import HfApi, hf_hub_download
    except ImportError as exc:
        raise OfflineModelUnavailable(
            "Offline download tools are missing. Install requirements-offline.txt first."
        ) from exc

    destination = model_path()
    destination.parent.mkdir(parents=True, exist_ok=True)
    try:
        filenames = HfApi().list_repo_files(MODEL_REPO)
        candidates = [
            name for name in filenames
            if name.casefold().endswith("-q4_0.gguf")
        ]
        if not candidates:
            candidates = [
                name for name in filenames
                if name.casefold().endswith("-q4_k_m.gguf")
            ]
        if not candidates:
            raise OfflineModelUnavailable(
                "The official model repository did not contain a supported Q4 GGUF file."
            )
        selected = sorted(candidates, key=lambda name: (len(name), name))[0]
        downloaded = Path(
            hf_hub_download(
                repo_id=MODEL_REPO,
                filename=selected,
                local_dir=str(destination.parent),
            )
        )
        if os.getenv("HOMER_OFFLINE_MODEL_PATH", "").strip():
            target = destination
        else:
            target = destination.parent / Path(selected).name
        if downloaded.resolve() != target.resolve():
            target.write_bytes(downloaded.read_bytes())
        if not target.is_file() or target.stat().st_size < 100_000_000:
            raise OfflineModelUnavailable("The downloaded GGUF file is incomplete.")
        return target
    except OfflineModelUnavailable:
        raise
    except Exception as exc:
        raise OfflineModelUnavailable(
            "Could not download the offline model. Check internet access and try again."
        ) from exc


def _load_model():
    """Load one CPU-only model instance on first offline request."""
    global _model
    with _model_lock:
        if _model is not None:
            return _model

        path = model_path()
        if not path.is_file() or path.stat().st_size < 100_000_000:
            raise OfflineModelUnavailable(
                "The offline model is not installed. While online, run: "
                "python -m app.ai.offline_model download"
            )
        try:
            import psutil
            available_mb = psutil.virtual_memory().available / (1024 * 1024)
            if available_mb < 800:
                raise OfflineModelUnavailable(
                    f"Only {available_mb:.0f} MB RAM is available; close other apps and try again."
                )
        except ImportError:
            # psutil is a core HOMER dependency, but keep a useful fallback if
            # a minimal custom install omitted it.
            pass

        try:
            from llama_cpp import Llama
        except ImportError as exc:
            raise OfflineModelUnavailable(
                "The offline runtime is not installed. Run: "
                "python -m pip install -r requirements-offline.txt"
            ) from exc

        try:
            context_size = int(os.getenv("HOMER_OFFLINE_CONTEXT", "1536"))
            threads = int(os.getenv("HOMER_OFFLINE_THREADS", "2"))
            if not 512 <= context_size <= 4096:
                raise ValueError("HOMER_OFFLINE_CONTEXT must be between 512 and 4096.")
            if not 1 <= threads <= 8:
                raise ValueError("HOMER_OFFLINE_THREADS must be between 1 and 8.")
            _model = Llama(
                model_path=str(path),
                n_ctx=context_size,
                n_threads=threads,
                n_batch=64,
                n_gpu_layers=0,
                use_mmap=True,
                use_mlock=False,
                verbose=False,
            )
            return _model
        except Exception as exc:
            raise OfflineModelUnavailable(
                "The local GGUF model could not be loaded. Check available RAM and the model file."
            ) from exc


def generate_reply(messages: list[dict[str, str]]) -> str:
    """Generate one concise response locally without network or GPU access."""
    if not messages:
        raise ValueError("At least one chat message is required.")
    with _model_lock:
        model = _load_model()
        try:
            max_tokens = int(os.getenv("HOMER_OFFLINE_MAX_TOKENS", "256"))
            if not 64 <= max_tokens <= 1024:
                raise ValueError("HOMER_OFFLINE_MAX_TOKENS must be between 64 and 1024.")
            result = model.create_chat_completion(
                messages=messages,
                temperature=0.35,
                top_p=0.9,
                max_tokens=max_tokens,
                repeat_penalty=1.1,
            )
            answer = result["choices"][0]["message"].get("content")
            if not isinstance(answer, str) or not answer.strip():
                raise OfflineModelUnavailable("The offline model returned an empty response.")
            return answer.strip()
        except OfflineModelUnavailable:
            raise
        except Exception as exc:
            raise OfflineModelUnavailable(
                "The offline model failed to generate a response."
            ) from exc


def _main() -> int:
    parser = argparse.ArgumentParser(description="Manage HOMER's optional offline AI model.")
    parser.add_argument("action", choices=("download", "status"))
    args = parser.parse_args()
    if args.action == "download":
        print("Downloading the Qwen2.5 0.5B Q4 model (approximately 430 MB)...")
        path = download_model()
        print(f"Offline model ready: {path}")
    else:
        status = model_status()
        print(status)
        if not status["ready"]:
            print("Run: python -m app.ai.offline_model download")
            return 1
    return 0


def unload_model() -> None:
    """Release the offline model after Groq becomes available again."""
    global _model
    with _model_lock:
        model = _model
        _model = None
        if model is not None:
            close = getattr(model, "close", None)
            if callable(close):
                close()
            del model


if __name__ == "__main__":
    raise SystemExit(_main())
