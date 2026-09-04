"""
Central AI Quant Brain Orchestrator.
Receives user messages, maintains session context, invokes MCP tools,
and produces evidence-grounded market intelligence.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Dict, List, Optional
from brain.context import extract_symbol_and_timeframe
from brain.intent_classifier import classify_query_intent, select_tools_for_intent, QueryIntent
from brain.llm_client import quant_llm_client
from mcp_tools.registry import mcp_registry
from storage.repository import QuantBrainRepository

logger = logging.getLogger(__name__)


class QuantBrainOrchestrator:
    """Master orchestrator connecting user queries to MCP tools and Quant Brain reasoning."""

    async def process_query(
        self,
        session_id: str,
        user_message: str,
        channel: str = "web",
    ) -> Dict[str, Any]:
        """
        Process a user's natural language question with full context continuity.
        """
        start_time = time.time()
        logger.info("[%s] User Query: '%s' (Session: %s)", channel.upper(), user_message, session_id)

        # 1. Fetch current conversation context & message history
        context = await QuantBrainRepository.get_active_context(session_id)
        raw_history = await QuantBrainRepository.get_messages(session_id=session_id, limit=6)
        conversation_history = [
            {"role": m.role, "content": m.content}
            for m in reversed(raw_history)
            if m.content and not m.content.startswith("⛔")
        ]

        # 2. Extract active symbol & timeframe (inherits from context if follow-up)
        symbol, timeframe, was_symbol_explicit = extract_symbol_and_timeframe(
            user_message, current_context=context
        )

        # 3. Classify intent
        intent = classify_query_intent(user_message)
        logger.info("Identified Intent: %s | Active Symbol: %s | Timeframe: %s", intent.value, symbol, timeframe)

        # 4. Select and invoke minimal required MCP tools
        tool_calls = select_tools_for_intent(intent, symbol=symbol, timeframe=timeframe)
        tool_tasks = [mcp_registry.call_tool(t["tool"], t["args"]) for t in tool_calls]
        tool_outputs = await asyncio.gather(*tool_tasks, return_exceptions=True)

        tool_results: Dict[str, Any] = {}
        for call_spec, out in zip(tool_calls, tool_outputs):
            tool_name = call_spec["tool"]
            if isinstance(out, dict) and out.get("status") == "success":
                tool_results[tool_name] = out.get("data")
            elif isinstance(out, dict) and "error" in out:
                tool_results[tool_name] = {"error": out["error"]}
            elif isinstance(out, Exception):
                tool_results[tool_name] = {"error": str(out)}

        # 5. Generate AI response
        gen_result = await quant_llm_client.generate_response(
            user_query=user_message,
            intent=intent,
            symbol=symbol,
            timeframe=timeframe,
            tool_results=tool_results,
            conversation_history=conversation_history,
        )

        if isinstance(gen_result, tuple):
            ai_response, engine_used = gen_result
        else:
            ai_response = gen_result
            engine_used = "Deterministic Quant Engine"

        total_latency = round((time.time() - start_time) * 1000, 2)

        # 6. Update context & save message history
        await QuantBrainRepository.update_active_context(
            session_id=session_id,
            symbol=symbol,
            timeframe=timeframe,
            topic=intent.value,
        )

        # Save user message & assistant reply
        await QuantBrainRepository.save_message(
            session_id=session_id,
            role="user",
            content=user_message,
            channel=channel,
            metadata={"intent": intent.value, "symbol": symbol, "timeframe": timeframe},
        )
        await QuantBrainRepository.save_message(
            session_id=session_id,
            role="assistant",
            content=ai_response,
            channel=channel,
            metadata={"latency_ms": total_latency, "engine": engine_used, "tools_called": [t["tool"] for t in tool_calls]},
        )

        return {
            "session_id": session_id,
            "symbol": symbol,
            "timeframe": timeframe,
            "intent": intent.value,
            "response": ai_response,
            "engine": engine_used,
            "tools_called": [t["tool"] for t in tool_calls],
            "latency_ms": total_latency,
            "timestamp": time.time(),
        }


# Global singleton orchestrator
quant_brain = QuantBrainOrchestrator()
