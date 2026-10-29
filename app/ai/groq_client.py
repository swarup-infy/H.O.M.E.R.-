"""Groq API adapter for HOMER with one controlled tool-call cycle."""

import json
import logging
from typing import Any

from groq import AsyncGroq

from app.config import get_settings
from app.tools.registry import TOOL_DEFINITIONS, execute_tool

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are HOMER, a friendly, intelligent Windows desktop AI assistant.

IDENTITY:
- Your name is HOMER.
- You are NEVER JARVIS. Never introduce yourself as JARVIS.
- If asked your name, say: "I'm HOMER, your Windows desktop assistant."
- If asked to introduce yourself, introduce yourself as HOMER.
- Speak naturally, clearly, and helpfully.

PERSONALITY:
- Be friendly, intelligent, occasionally funny, and respectful.
- Help the user answer questions and complete tasks.
- Use available tools only when appropriate and safe.
- Never claim you performed an action unless it actually succeeded.
"""


class AIProviderNotConfigured(RuntimeError):
    """Raised when the API key is missing."""


async def ask_homer(user_message: str) -> str:
    """Send a message to Groq and execute at most one approved tool call."""
    settings = get_settings()

    if not settings.groq_api_key or settings.groq_api_key == "replace_me":
        raise AIProviderNotConfigured(
            "GROQ_API_KEY is missing. Copy .env.example to .env and add your key."
        )

    client = AsyncGroq(api_key=settings.groq_api_key)

    messages: list[dict[str, Any]] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_message},
    ]

    try:
        first_response = await client.chat.completions.create(
            model=settings.groq_model,
            messages=messages,
            tools=TOOL_DEFINITIONS,
            tool_choice="auto",
            temperature=0.2,
            max_completion_tokens=500,
        )

        assistant_message = first_response.choices[0].message
        tool_calls = assistant_message.tool_calls or []

        if not tool_calls:
            return assistant_message.content or "I couldn't generate a text response."

        # Execute at most one tool call in this MVP.
        tool_call = tool_calls[0]
        tool_name = tool_call.function.name

        try:
            arguments = json.loads(tool_call.function.arguments or "{}")
            if not isinstance(arguments, dict):
                arguments = {"_invalid_arguments": arguments}
        except json.JSONDecodeError:
            arguments = {"_invalid_arguments": "Malformed JSON"}

        tool_result = execute_tool(tool_name, arguments)

        messages.append(assistant_message.model_dump(exclude_none=True))
        messages.append(
            {
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": json.dumps(tool_result),
            }
        )

        final_response = await client.chat.completions.create(
            model=settings.groq_model,
            messages=messages,
            tools=TOOL_DEFINITIONS,
            tool_choice="none",
            temperature=0.2,
            max_completion_tokens=500,
        )

        final_text = final_response.choices[0].message.content
        return final_text or json.dumps(tool_result)

    except Exception as exc:
        logger.exception("Groq request failed (%s)", type(exc).__name__)
        raise RuntimeError(
            "The AI provider request failed. Check your internet connection, API key, "
            "account access, and configured model ID."
        ) from exc

    finally:
        await client.close()