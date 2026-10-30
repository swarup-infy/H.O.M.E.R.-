"""Groq API adapter for HOMER with one controlled tool-call cycle."""

import json
import logging
import asyncio
from typing import Any

from groq import AsyncGroq

from app.config import get_settings
from app.tools.registry import TOOL_DEFINITIONS, execute_tool

logger = logging.getLogger(__name__)

# Keep only a small recent window so follow-up questions have context.
_MAX_HISTORY_MESSAGES = 12
_history: list[dict[str, Any]] = []
_history_lock = asyncio.Lock()

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
- When the user asks to close the current window, call close_active_window; warn briefly that unsaved work may prompt for confirmation.
- When asked to minimize the current window, call minimize_active_window.
- For play/pause, pause/resume, or toggle playback on the current media session, call media_play_pause.
- For next/skip track or previous track, call the matching media tool.
- For a YouTube timestamp such as "go to 6 minutes", call seek_youtube_to_time with seconds=360. Convert minutes and seconds accurately. Tell the user to focus the YouTube video tab first if needed.
- For "play [song/video] on YouTube", use play_youtube_video with the actual song/video query, not open_website search results. For "open YouTube" without a play request, use open_website. Opening a watch page does not guarantee autoplay; never claim playback started unless confirmed.\n- When the user names a window to close, such as "close Brave", use close_named_window with that application. Do not close unrelated windows.\n- For requests to inspect the desktop or locate a visible control, use inspect_screen first. For an explicit click request such as "click Play", use click_screen_target with a concise target description. UI Automation is preferred; visual coordinates are the fallback. Never claim that a click started playback without checking the resulting state.\n- Reuse the current browser tab for ordinary open/search tasks; do not repeatedly launch windows for the same task.
- Only use the listed tools for computer actions. Never invent a successful action.

VOICE-FIRST RESPONSE LENGTH:
- Default to a concise answer suitable for spoken conversation: usually 1–3 short sentences.
- For a simple question, answer directly; do not add long introductions, repeated summaries, or unnecessary lists.
- Give a longer explanation only when the user explicitly asks for detail, steps, examples, or a comprehensive answer.
- Keep spoken answers easy to understand aloud.
"""


class AIProviderNotConfigured(RuntimeError):
    """Raised when the API key is missing."""


async def clear_history() -> None:
    """Forget the in-memory conversation so the next chat starts clean."""
    async with _history_lock:
        _history.clear()


async def ask_homer(user_message: str) -> str:
    """Send a message to Groq with bounded short-term conversation context."""
    settings = get_settings()

    if not settings.groq_api_key or settings.groq_api_key == "replace_me":
        raise AIProviderNotConfigured(
            "GROQ_API_KEY is missing. Copy .env.example to .env and add your key."
        )

    client = AsyncGroq(api_key=settings.groq_api_key)

    async with _history_lock:
        history = list(_history)
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        *history,
        {"role": "user", "content": user_message},
    ]

    try:
        first_response = await client.chat.completions.create(
            model=settings.groq_model,
            messages=messages,
            tools=TOOL_DEFINITIONS,
            tool_choice="auto",
            temperature=0.2,
            max_completion_tokens=300,
        )

        response = first_response
        tool_steps = 0
        last_tool_result: dict[str, Any] | None = None

        # Permit a short, bounded sequence of tool calls for multi-step requests.
        # Every action still passes through the strict allowlist in registry.py.
        while tool_steps < 4:
            assistant_message = response.choices[0].message
            tool_calls = assistant_message.tool_calls or []
            if not tool_calls:
                final_text = assistant_message.content or (
                    json.dumps(last_tool_result) if last_tool_result else
                    "I couldn't generate a text response."
                )
                break

            messages.append(assistant_message.model_dump(exclude_none=True))
            for tool_call in tool_calls[:4 - tool_steps]:
                tool_name = tool_call.function.name
                try:
                    arguments = json.loads(tool_call.function.arguments or "{}")
                    if not isinstance(arguments, dict):
                        arguments = {"_invalid_arguments": arguments}
                except json.JSONDecodeError:
                    arguments = {"_invalid_arguments": "Malformed JSON"}

                tool_result = execute_tool(tool_name, arguments)
                last_tool_result = tool_result
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": json.dumps(tool_result),
                })
                tool_steps += 1

            if tool_steps >= 4:
                break

            response = await client.chat.completions.create(
                model=settings.groq_model,
                messages=messages,
                tools=TOOL_DEFINITIONS,
                tool_choice="auto",
                temperature=0.2,
                max_completion_tokens=400,
            )
        else:
            final_text = (
                "I completed the allowed actions for this request. "
                "Ask me to continue if there are more steps."
            )

        if tool_steps >= 4 and (response.choices[0].message.tool_calls or []):
            final_text = (
                "I reached the four-action safety limit for one request. "
                "Tell me to continue if you want the next steps."
            )
        elif tool_steps and 'final_text' not in locals():
            final_response = await client.chat.completions.create(
                model=settings.groq_model,
                messages=messages,
                tools=TOOL_DEFINITIONS,
                tool_choice="none",
                temperature=0.2,
                max_completion_tokens=400,
            )
            final_text = final_response.choices[0].message.content or json.dumps(last_tool_result)
        async with _history_lock:
            _history.extend([
                {"role": "user", "content": user_message},
                {"role": "assistant", "content": final_text},
            ])
            del _history[:-_MAX_HISTORY_MESSAGES]
        return final_text

    except Exception as exc:
        logger.exception("Groq request failed (%s)", type(exc).__name__)
        raise RuntimeError(
            "The AI provider request failed. Check your internet connection, API key, "
            "account access, and configured model ID."
        ) from exc

    finally:
        await client.close()