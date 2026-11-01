"""Small environment-based configuration for the first JARVIS prototype."""

import os
from functools import lru_cache

from dotenv import load_dotenv

load_dotenv()


class Settings:
    """Application settings loaded from environment variables."""

    def __init__(self) -> None:
        self.groq_api_key = os.getenv("GROQ_API_KEY", "").strip()
        self.groq_model = os.getenv("GROQ_MODEL", "openai/gpt-oss-20b").strip()
        self.groq_vision_model = os.getenv("GROQ_VISION_MODEL", "qwen/qwen3.8-27b").strip()
        self.max_message_chars = 2000


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
