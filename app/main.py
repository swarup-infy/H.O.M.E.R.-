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
        max_length=2000,
        description="User message for HOMER",
    )


class ChatResponse(BaseModel):
    reply: str


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
        "provider": "groq",
        "model": settings.groq_model,
        "api_key_configured": bool(settings.groq_api_key),
    }


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