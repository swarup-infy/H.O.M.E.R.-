"""Validated environment-based settings for the HOMER desktop assistant."""

import os
from functools import lru_cache

from dotenv import load_dotenv

load_dotenv()


def _read_int(name: str, default: int, *, minimum: int, maximum: int) -> int:
    raw = os.getenv(name, str(default)).strip()
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer.") from exc
    if not minimum <= value <= maximum:
        raise ValueError(f"{name} must be between {minimum} and {maximum}.")
    return value


def _read_float(name: str, default: float, *, minimum: float, maximum: float) -> float:
    raw = os.getenv(name, str(default)).strip()
    try:
        value = float(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be a number.") from exc
    if not minimum <= value <= maximum:
        raise ValueError(f"{name} must be between {minimum} and {maximum}.")
    return value


class Settings:
    """Application settings loaded and validated from environment variables."""

    def __init__(self) -> None:
        self.llm_provider = os.getenv("LLM_PROVIDER", "groq").strip().lower()
        if self.llm_provider != "groq":
            raise ValueError("LLM_PROVIDER currently supports only 'groq'.")

        self.groq_api_key = os.getenv("GROQ_API_KEY", "").strip()
        self.groq_model = os.getenv("GROQ_MODEL", "openai/gpt-oss-20b").strip()
        self.groq_vision_model = os.getenv(
            "GROQ_VISION_MODEL", "qwen/qwen3.8-27b"
        ).strip()
        if not self.groq_model:
            raise ValueError("GROQ_MODEL cannot be empty.")
        if not self.groq_vision_model:
            raise ValueError("GROQ_VISION_MODEL cannot be empty.")

        self.groq_temperature = _read_float(
            "GROQ_TEMPERATURE", 0.2, minimum=0.0, maximum=2.0
        )
        self.groq_top_p = _read_float(
            "GROQ_TOP_P", 1.0, minimum=0.0, maximum=1.0
        )
        self.groq_max_output_tokens = _read_int(
            "GROQ_MAX_OUTPUT_TOKENS", 2048, minimum=1, maximum=32768
        )
        self.groq_reasoning_effort = os.getenv(
            "GROQ_REASONING_EFFORT", "medium"
        ).strip().lower()
        if self.groq_reasoning_effort not in {"low", "medium", "high"}:
            raise ValueError(
                "GROQ_REASONING_EFFORT must be one of: low, medium, high."
            )
        self.groq_timeout_seconds = _read_float(
            "GROQ_TIMEOUT_SECONDS", 45.0, minimum=1.0, maximum=300.0
        )
        self.groq_max_retries = _read_int(
            "GROQ_MAX_RETRIES", 2, minimum=0, maximum=5
        )
        self.chat_history_messages = _read_int(
            "HOMER_CHAT_HISTORY_MESSAGES", 12, minimum=2, maximum=100
        )
        if self.chat_history_messages % 2:
            raise ValueError("HOMER_CHAT_HISTORY_MESSAGES must be an even number.")
        self.max_message_chars = _read_int(
            "HOMER_MAX_MESSAGE_CHARS", 2000, minimum=1, maximum=20000
        )
        self.offline_fallback_enabled = os.getenv(
            "HOMER_OFFLINE_FALLBACK_ENABLED", "true"
        ).strip().lower() in {"1", "true", "yes", "on"}
        self.offline_threads = _read_int(
            "HOMER_OFFLINE_THREADS", 2, minimum=1, maximum=4
        )
        self.offline_max_tokens = _read_int(
            "HOMER_OFFLINE_MAX_TOKENS", 160, minimum=32, maximum=256
        )
        self.offline_context_tokens = 2048
        self.offline_model_name = "SmolLM2-360M-Instruct Q4_K_M"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the cached application settings instance."""
    return Settings()
