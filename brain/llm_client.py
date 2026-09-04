"""
LLM Client and Fallback Engine for Live Quant Brain.
Integrates with OpenAI, Google Gemini, or falls back to the deterministic Quant Reasoner.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional
from config.quant_brain_config import settings
from brain.reasoning import synthesize_quant_response
from brain.intent_classifier import QueryIntent

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """
You are the Live Quant Brain — a senior quant analyst and market intelligence engine.
Your purpose is decision support and objective market analysis, NOT blind trade recommendations or financial advice.

CRITICAL RULES:
1. NEVER hallucinate prices, volume, support/resistance, or market events. Only use numbers provided in the tool results.
2. If data is delayed or marked unavailable, explicitly state: "Data is delayed" or "Market data unavailable from the connected source."
3. Distinguish clearly between:
   - OBSERVED: Verifiable factual numbers.
   - INFERRED: Probabilistic transmission mechanisms.
   - UNKNOWN: Unconfirmed catalysts or missing information.
4. For broad queries, format response strictly using:
   📊 MARKET
   📈 TREND
   🏗 STRUCTURE
   💧 LIQUIDITY
   📦 VOLUME / MOMENTUM
   📰 DRIVERS
   🎯 SCENARIOS
   👀 WATCH
5. For short specific questions (e.g. price, simple trend, liquidity), give direct, concise answers with evidence.
"""


class QuantLLMClient:
    """Manages AI reasoning via OpenAI, Gemini LLM, or deterministic rule-based engine."""

    def __init__(self) -> None:
        self.openai_client = None
        self.gemini_client = None
        self.openai_quota_exhausted: bool = False
        self.last_error_message: Optional[str] = None
        self._init_clients()

    def _init_clients(self) -> None:
        import os
        openai_key = settings.OPENAI_API_KEY or os.getenv("OPENAI_API_KEY")
        if openai_key:
            try:
                from openai import OpenAI
                base_url = os.getenv("OPENAI_BASE_URL") or None
                self.openai_client = OpenAI(api_key=openai_key.strip(), base_url=base_url, max_retries=0, timeout=12.0)
                logger.info("Initialized OpenAI client with model %s", settings.OPENAI_MODEL)
            except Exception as e:
                logger.warning("Could not initialize OpenAI client: %s", e)

        gemini_key = settings.GEMINI_API_KEY or os.getenv("GEMINI_API_KEY")
        if gemini_key:
            try:
                from google import genai
                self.gemini_client = genai.Client(api_key=gemini_key.strip())
                logger.info("Initialized Google Gemini client with model %s", settings.GEMINI_MODEL)
            except Exception as e:
                logger.warning("Could not initialize Gemini client: %s", e)

    def _ensure_clients(self) -> None:
        import os
        if self.openai_client is None:
            openai_key = settings.OPENAI_API_KEY or os.getenv("OPENAI_API_KEY")
            if openai_key:
                try:
                    from openai import OpenAI
                    base_url = os.getenv("OPENAI_BASE_URL") or None
                    self.openai_client = OpenAI(api_key=openai_key.strip(), base_url=base_url, max_retries=0, timeout=12.0)
                    logger.info("Initialized OpenAI client dynamically with model %s", settings.OPENAI_MODEL)
                except Exception as e:
                    logger.warning("Could not initialize OpenAI client dynamically: %s", e)

        if self.gemini_client is None:
            gemini_key = settings.GEMINI_API_KEY or os.getenv("GEMINI_API_KEY")
            if gemini_key:
                try:
                    from google import genai
                    self.gemini_client = genai.Client(api_key=gemini_key.strip())
                    logger.info("Initialized Gemini client dynamically with model %s", settings.GEMINI_MODEL)
                except Exception as e:
                    logger.warning("Could not initialize Gemini client dynamically: %s", e)

    async def generate_response(
        self,
        user_query: str,
        intent: QueryIntent,
        symbol: str,
        timeframe: str,
        tool_results: Dict[str, Any],
        conversation_history: Optional[List[Dict[str, str]]] = None,
    ) -> Any:
        """
        Generates analysis response using OpenAI or Gemini LLM if available,
        otherwise falls back to deterministic quant synthesizer.
        Returns: (response_text, engine_name)
        """
        import asyncio

        self._ensure_clients()

        prompt_content = (
            f"User Query: {user_query}\n"
            f"Active Symbol: {symbol}\n"
            f"Active Timeframe: {timeframe}\n"
            f"Intent: {intent.value}\n\n"
            f"VERIFIED REAL-TIME QUANTITATIVE TOOL RESULTS (Use ONLY this data, NEVER fabricate):\n"
            f"{json.dumps(tool_results, default=str, indent=2)}\n\n"
            "Synthesize a rigorous, institutional, quantitative, evidence-based response following the required format."
        )

        # 1. Try OpenAI if API key available and provider is 'openai' or 'auto'
        if self.openai_client and settings.AI_PROVIDER in ("openai", "auto") and not self.openai_quota_exhausted:
            try:
                def _call_openai():
                    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
                    if conversation_history:
                        for msg in conversation_history[-6:]:
                            role = msg.get("role", "user")
                            if role in ("user", "assistant"):
                                messages.append({"role": role, "content": msg.get("content", "")})
                    messages.append({"role": "user", "content": prompt_content})
                    completion = self.openai_client.chat.completions.create(
                        model=settings.OPENAI_MODEL,
                        messages=messages,
                        temperature=0.2,
                        max_tokens=1200,
                    )
                    return completion.choices[0].message.content

                response_text = await asyncio.to_thread(_call_openai)
                if response_text and len(response_text.strip()) > 20:
                    engine_name = f"OpenAI ({settings.OPENAI_MODEL})"
                    return response_text.strip(), engine_name
            except Exception as e:
                err_str = str(e)
                if "insufficient_quota" in err_str or "credit_balance_exhausted" in err_str or "429" in err_str:
                    self.openai_quota_exhausted = True
                    self.last_error_message = "OpenAI credit balance exhausted ($0 credits). Add credits at platform.openai.com/billing."
                    logger.warning("OpenAI quota exhausted (Error 429: credit_balance_exhausted). Falling back to Gemini or Deterministic Quant Engine.")
                else:
                    self.last_error_message = err_str[:160]
                    logger.error("OpenAI API generation error: %s, checking alternatives", e)

        # 2. Try Gemini if API key available and provider is 'gemini' or 'auto'
        if self.gemini_client and settings.AI_PROVIDER in ("gemini", "auto"):
            try:
                def _call_gemini():
                    response = self.gemini_client.models.generate_content(
                        model=settings.GEMINI_MODEL,
                        contents=[prompt_content],
                        config={"system_instruction": SYSTEM_PROMPT},
                    )
                    return response.text

                response_text = await asyncio.to_thread(_call_gemini)
                if response_text and len(response_text.strip()) > 20:
                    engine_name = f"Google Gemini ({settings.GEMINI_MODEL})"
                    return response_text.strip(), engine_name
            except Exception as e:
                logger.error("Gemini API generation error: %s, falling back to deterministic synthesizer", e)

        # 3. Deterministic high-precision quant fallback
        synth = synthesize_quant_response(
            intent=intent,
            user_query=user_query,
            symbol=symbol,
            timeframe=timeframe,
            tool_results=tool_results,
        )

        engine_name = "Deterministic Quant Engine"
        if self.openai_quota_exhausted:
            engine_name = "Deterministic Engine (OpenAI Quota Exhausted)"
            if intent != QueryIntent.GREETING:
                synth += (
                    "\n\n---\n"
                    "💡 **AI Engine Status**: Your OpenAI API key is verified and connected, but OpenAI returned Error 429 (`credit_balance_exhausted`: $0.00 credit balance). "
                    "To activate GPT-4o-mini, add $5 credit to your OpenAI account at [platform.openai.com/billing](https://platform.openai.com/settings/organization/billing/) "
                    "or add a free Google Gemini API key (`GEMINI_API_KEY`) to `.env`."
                )

        return synth, engine_name


# Global singleton LLM client
quant_llm_client = QuantLLMClient()
