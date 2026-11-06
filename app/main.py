"""FastAPI entry point for the HOMER API-first MVP."""

import logging
import base64
import binascii

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from app.ai.groq_client import AIProviderNotConfigured, ask_homer, clear_history
from app.ai.vision_client import ask_about_image
from app.config import get_settings
from app.jobs.routes import router as jobs_router

logging.basicConfig(level=logging.INFO)

app = FastAPI(
    title="HOMER API MVP",
    description="API-first desktop assistant prototype with a single allowlisted action.",
    version="0.1.0",
)
app.include_router(jobs_router)


class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    message: str = Field(
        min_length=1,
        max_length=20000,
        description="User message for HOMER",
    )


class ChatResponse(BaseModel):
    reply: str


class ChatSettingsResponse(BaseModel):
    """Safe-to-display chat settings; never includes provider credentials."""

    provider: str
    model: str
    temperature: float
    top_p: float
    max_output_tokens: int
    timeout_seconds: float
    max_retries: int
    history_messages: int
    max_message_chars: int
    api_key_configured: bool


class ScreenQuestion(BaseModel):
    model_config = ConfigDict(extra="forbid")
    prompt: str = Field(min_length=1, max_length=1000)
    image_data_url: str = Field(min_length=1, max_length=8_000_000)


@app.get("/health")
async def health() -> dict[str, str | bool]:
    """Report app status without exposing credentials."""
    settings = get_settings()

    return {
        "status": "ok",
        "provider": settings.llm_provider,
        "model": settings.groq_model,
        "api_key_configured": bool(settings.groq_api_key),
    }


@app.get("/chat/settings", response_model=ChatSettingsResponse)
async def chat_settings() -> ChatSettingsResponse:
    """Return the active chat configuration without exposing secrets."""
    settings = get_settings()
    return ChatSettingsResponse(
        provider=settings.llm_provider,
        model=settings.groq_model,
        temperature=settings.groq_temperature,
        top_p=settings.groq_top_p,
        max_output_tokens=settings.groq_max_output_tokens,
        timeout_seconds=settings.groq_timeout_seconds,
        max_retries=settings.groq_max_retries,
        history_messages=settings.chat_history_messages,
        max_message_chars=settings.max_message_chars,
        api_key_configured=bool(
            settings.groq_api_key and settings.groq_api_key != "replace_me"
        ),
    )


@app.post("/chat/reset")
async def reset_chat() -> dict[str, str]:
    """Clear HOMER's short-term conversation context for a fresh chat."""
    await clear_history()
    return {"status": "ok", "message": "Conversation context cleared."}


@app.post("/screen/ask", response_model=ChatResponse)
async def screen_ask(request: ScreenQuestion) -> ChatResponse:
    """Analyze one user-selected screenshot; never capture the screen on the server."""
    prefix = "data:image/jpeg;base64,"
    if not request.image_data_url.startswith(prefix):
        raise HTTPException(status_code=422, detail="Expected a JPEG data URL.")
    encoded = request.image_data_url[len(prefix):]
    try:
        image_bytes = base64.b64decode(encoded, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise HTTPException(status_code=422, detail="Invalid screenshot encoding.") from exc
    if not image_bytes or len(image_bytes) > 5_000_000:
        raise HTTPException(status_code=413, detail="Screenshot must be under 5 MB.")
    try:
        reply = await ask_about_image(request.prompt.strip(), request.image_data_url)
        return ChatResponse(reply=reply)
    except RuntimeError as exc:
        logging.getLogger(__name__).exception("Screen vision request failed")
        raise HTTPException(status_code=502, detail="Vision request failed. Check server logs, model access, and API configuration.") from exc


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    message = request.message.strip()
    settings = get_settings()

    if len(message) > settings.max_message_chars:
        raise HTTPException(
            status_code=422,
            detail=f"Message cannot exceed {settings.max_message_chars} characters.",
        )

    if not message:
        raise HTTPException(
            status_code=422,
            detail="Message cannot be blank.",
        )

    try:
        reply = await ask_homer(message)
        return ChatResponse(reply=reply)

    except AIProviderNotConfigured as exc:
        raise HTTPException(
            status_code=503,
            detail=str(exc),
        ) from exc

    except RuntimeError as exc:
        # Keep provider diagnostics in server logs.
        # Never expose internal exception details to clients.
        logging.getLogger(__name__).exception(
            "Chat provider request failed"
        )

        raise HTTPException(
            status_code=502,
            detail=(
                "The AI provider request failed. "
                "Check server logs and provider configuration."
            ),
        ) from exc