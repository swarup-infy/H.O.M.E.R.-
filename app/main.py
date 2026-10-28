"""FastAPI entry point for the JARVIS API-first MVP."""

import logging

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from app.ai.groq_client import AIProviderNotConfigured, ask_jarvis
from app.config import get_settings

logging.basicConfig(level=logging.INFO)

app = FastAPI(
    title="JARVIS API MVP",
    description="API-first desktop assistant prototype with a single allowlisted action.",
    version="0.1.0",
)


class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    message: str = Field(min_length=1, max_length=2000, description="User message for JARVIS")


class ChatResponse(BaseModel):
    reply: str


@app.get("/health")
async def health() -> dict[str, str | bool]:
    """Report app status without exposing credentials."""
    settings = get_settings()
    key_configured = bool(settings.groq_api_key and settings.groq_api_key != "replace_me")
    return {
        "status": "ok",
        "provider": "groq",
        "model": settings.groq_model,
        "api_key_configured": key_configured,
    }


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    message = request.message.strip()
    if not message:
        raise HTTPException(status_code=422, detail="Message cannot be blank.")

    try:
        reply = await ask_jarvis(message)
        return ChatResponse(reply=reply)
    except AIProviderNotConfigured as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except RuntimeError as exc:
        # Keep provider diagnostics in server logs; never return internal
        # exception text (which may contain URLs or sensitive details) to clients.
        logging.getLogger(__name__).exception("Chat provider request failed")
        raise HTTPException(
            status_code=502,
            detail="The AI provider request failed. Check server logs and provider configuration.",
        ) from exc
