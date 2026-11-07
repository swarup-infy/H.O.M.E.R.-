"""Validation tests for HOMER's environment-based chat settings."""

import pytest

from app.config import Settings


SETTING_ENV_VARS = (
    "LLM_PROVIDER",
    "GROQ_API_KEY",
    "GROQ_MODEL",
    "GROQ_VISION_MODEL",
    "GROQ_TEMPERATURE",
    "GROQ_TOP_P",
    "GROQ_MAX_OUTPUT_TOKENS",
    "GROQ_REASONING_EFFORT",
    "GROQ_TIMEOUT_SECONDS",
    "GROQ_MAX_RETRIES",
    "HOMER_CHAT_HISTORY_MESSAGES",
    "HOMER_MAX_MESSAGE_CHARS",
    "HOMER_OFFLINE_FALLBACK",
    "HOMER_OFFLINE_MODEL_PATH",
    "HOMER_OFFLINE_CONTEXT",
    "HOMER_OFFLINE_THREADS",
    "HOMER_OFFLINE_MAX_TOKENS",
)


def clear_setting_environment(monkeypatch) -> None:
    for name in SETTING_ENV_VARS:
        monkeypatch.delenv(name, raising=False)


def test_settings_defaults_are_safe_and_documented(monkeypatch) -> None:
    clear_setting_environment(monkeypatch)
    settings = Settings()

    assert settings.llm_provider == "groq"
    assert settings.groq_model == "openai/gpt-oss-20b"
    assert settings.groq_temperature == 0.2
    assert settings.groq_top_p == 1.0
    assert settings.groq_max_output_tokens == 2048
    assert settings.groq_reasoning_effort == "medium"
    assert settings.groq_timeout_seconds == 45.0
    assert settings.groq_max_retries == 2
    assert settings.chat_history_messages == 12
    assert settings.max_message_chars == 2000


@pytest.mark.parametrize(
    ("name", "value", "message"),
    [
        ("LLM_PROVIDER", "openai", "only 'groq'"),
        ("GROQ_TEMPERATURE", "2.1", "between 0.0 and 2.0"),
        ("GROQ_TEMPERATURE", "warm", "must be a number"),
        ("GROQ_TOP_P", "-0.1", "between 0.0 and 1.0"),
        ("GROQ_MAX_OUTPUT_TOKENS", "0", "between 1 and 32768"),
        ("GROQ_MAX_OUTPUT_TOKENS", "many", "must be an integer"),
        ("GROQ_REASONING_EFFORT", "extreme", "must be one of: low, medium, high"),
        ("GROQ_TIMEOUT_SECONDS", "0", "between 1.0 and 300.0"),
        ("GROQ_MAX_RETRIES", "6", "between 0 and 5"),
        ("HOMER_CHAT_HISTORY_MESSAGES", "1", "between 2 and 100"),
        ("HOMER_CHAT_HISTORY_MESSAGES", "11", "must be an even number"),
        ("HOMER_MAX_MESSAGE_CHARS", "20001", "between 1 and 20000"),
    ],
)
def test_invalid_settings_fail_with_clear_message(
    monkeypatch, name: str, value: str, message: str
) -> None:
    clear_setting_environment(monkeypatch)
    monkeypatch.setenv(name, value)

    with pytest.raises(ValueError, match=message):
        Settings()


def test_empty_model_name_is_rejected(monkeypatch) -> None:
    clear_setting_environment(monkeypatch)
    monkeypatch.setenv("GROQ_MODEL", "   ")

    with pytest.raises(ValueError, match="GROQ_MODEL cannot be empty"):
        Settings()


def test_offline_fallback_defaults_to_enabled_but_is_not_loaded(monkeypatch) -> None:
    clear_setting_environment(monkeypatch)
    settings = Settings()
    assert settings.offline_fallback_enabled is True
    assert settings.offline_context == 1536
    assert settings.offline_threads == 2
    assert settings.offline_max_tokens == 256


def test_offline_fallback_can_be_disabled(monkeypatch) -> None:
    clear_setting_environment(monkeypatch)
    monkeypatch.setenv("HOMER_OFFLINE_FALLBACK", "false")
    assert Settings().offline_fallback_enabled is False


@pytest.mark.parametrize("value", ["maybe", "2", "enabled-ish"])
def test_invalid_offline_fallback_boolean_is_rejected(monkeypatch, value) -> None:
    clear_setting_environment(monkeypatch)
    monkeypatch.setenv("HOMER_OFFLINE_FALLBACK", value)
    with pytest.raises(ValueError, match="must be a boolean"):
        Settings()


@pytest.mark.parametrize(
    ("name", "value", "message"),
    [
        ("HOMER_OFFLINE_CONTEXT", "400", "between 512 and 4096"),
        ("HOMER_OFFLINE_THREADS", "0", "between 1 and 8"),
        ("HOMER_OFFLINE_MAX_TOKENS", "32", "between 64 and 1024"),
    ],
)
def test_offline_model_limits_are_validated(monkeypatch, name, value, message) -> None:
    clear_setting_environment(monkeypatch)
    monkeypatch.setenv(name, value)
    with pytest.raises(ValueError, match=message):
        Settings()
