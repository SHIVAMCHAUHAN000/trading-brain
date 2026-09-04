"""
AI Quant Chat API Route.
Shared endpoint powering both the Web Dashboard and API integrations.
"""

from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from brain.orchestrator import quant_brain
from storage.repository import QuantBrainRepository

router = APIRouter(prefix="/api/v1/chat", tags=["Chat"])


class ChatRequest(BaseModel):
    message: str = Field(description="Natural language question or command")
    session_id: Optional[str] = Field(default=None, description="Unique session ID for conversation memory")
    channel: str = Field(default="web", description="Originating channel: 'web', 'api'")


class ChatResponse(BaseModel):
    session_id: str
    symbol: str
    timeframe: str
    intent: str
    response: str
    engine: str = Field(default="Deterministic Quant Engine", description="AI / LLM model that generated the response")
    tools_called: List[str]
    latency_ms: float
    timestamp: float


@router.post("", response_model=ChatResponse)
async def post_chat_message(req: ChatRequest):
    """Processes natural language query using the Quant Brain."""
    if not req.message or not req.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty.")

    session_id = req.session_id or f"web_session_{uuid.uuid4().hex[:8]}"
    result = await quant_brain.process_query(
        session_id=session_id,
        user_message=req.message.strip(),
        channel=req.channel,
    )
    return ChatResponse(**result)


@router.get("/history")
async def get_chat_history(session_id: str, limit: int = 20):
    """Retrieves conversation history for a given session."""
    messages = await QuantBrainRepository.get_messages(session_id=session_id, limit=limit)
    return {
        "session_id": session_id,
        "count": len(messages),
        "messages": [
            {
                "id": m.id,
                "role": m.role,
                "content": m.content,
                "channel": m.channel,
                "created_at": m.created_at.isoformat(),
            }
            for m in messages
        ],
    }
