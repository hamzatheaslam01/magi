"""FastAPI transport layer for the MAGI web interface."""

import json
import os
from collections.abc import AsyncIterator

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from dotenv import load_dotenv

from .models import AgentName
from .real_agents import RealAgent
from .streaming_debate import StreamingDebateEngine
from .llm.openrouter import OpenRouterProvider


load_dotenv()

app = FastAPI(
    title="MAGI API",
    version="1.0.0",
)

frontend_origin = os.getenv(
    "FRONTEND_ORIGIN",
    "http://localhost:3000",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[frontend_origin, "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class DebateRequest(BaseModel):
    """Request body for a MAGI debate."""

    question: str = Field(min_length=1, max_length=10000)


def build_engine() -> StreamingDebateEngine:
    """Create the MAGI agents using the existing OpenRouter provider."""

    provider = OpenRouterProvider(
        model="openrouter/free"
    )

    agents = [
        RealAgent(AgentName.MELCHIOR, provider),
        RealAgent(AgentName.BALTHASAR, provider),
        RealAgent(AgentName.CASPER, provider),
    ]

    return StreamingDebateEngine(agents)


def encode_sse(event: dict) -> str:
    """Encode one JSON event as a Server-Sent Events message."""
    return f"data: {json.dumps(event, ensure_ascii=False)}\n\n"


@app.get("/api/health")
async def health() -> dict[str, str]:
    """Return backend availability."""
    return {"status": "online"}


@app.post("/api/debate")
async def debate(request: DebateRequest):
    """Run a complete debate and return the final backend state."""
    try:
        engine = build_engine()
        events = [event async for event in engine.stream(request.question.strip())]
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    completed = next(
        (event for event in reversed(events) if event["type"] == "completed"),
        None,
    )

    if completed is None:
        raise HTTPException(
            status_code=500,
            detail="MAGI debate ended without a final state.",
        )

    return completed


@app.post("/api/debate/stream")
async def debate_stream(request: DebateRequest):
    """Stream real MAGI round and agent events over SSE."""

    async def event_generator() -> AsyncIterator[str]:
        try:
            engine = build_engine()

            async for event in engine.stream(request.question.strip()):
                yield encode_sse(event)

        except Exception as exc:
            yield encode_sse(
                {
                    "type": "error",
                    "message": str(exc),
                }
            )

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
