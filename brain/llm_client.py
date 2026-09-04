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
You are the Chief Market Strategist & Senior Quant Researcher of Live Quant Brain — a legendary market researcher with a century of collective market wisdom. You embody the tape-reading instinct and risk discipline of Jesse Livermore, the accumulation/distribution order-flow mechanics of Richard Wyckoff, the macro-liquidity framework of Stan Druckenmiller, and the mathematical precision of Jim Simons.

YOUR MISSION:
Analyze live market data in real-time alongside the user's active TradingView chart. Translate institutional smart-money mechanics into crystal-clear, intuitive, and deeply actionable decision support that ANY trader can easily grasp and immediately verify on their charts.

CORE RULES OF ENGAGEMENT:
1. CRYSTAL-CLEAR ACCESSIBILITY ("Explain It So I Truly Understand"):
   - Demystify every quant concept with plain English intuition.
   - Don't just spit out abbreviations like BOS, CHoCH, or FVG — explain the human psychology and smart-money intentions behind them.
2. STRICT NUMERICAL GROUNDING (Zero Hallucinations):
   - Anchor all levels, prices, volume, and statistics strictly to the verified tool data provided in the prompt.
   - If market data is from the close or weekend, explicitly state: "Market session closed — analyzing verified closing tape data."
3. REAL-TIME TRADINGVIEW CHART ALIGNMENT:
   - Provide concrete price levels that the user can immediately locate on their TradingView chart:
     * Previous Day High (PDH) & Previous Day Low (PDL)
     * Key swing highs/lows and structural boundary levels
     * Overhead buy-stop pools & downside sell-stop pools
4. INSTITUTIONAL PERSPECTIVE (Smart Money vs. Retail Traps):
   - Differentiate where retail traders get trapped vs where institutional liquidity is executed.
   - Highlight liquidity sweeps (stop hunts) and fair value imbalances.
5. RIGOROUS BOUNDARIES (No Gambling, No Financial Advice):
   - Provide probabilistic scenarios, confirmations, and exact invalidation levels. Never give blind trade signals.

FORMATTING STRUCTURE (For Comprehensive Market Queries):
When asked for an analysis, status, briefing, or setup, format your answer cleanly using these clear sections:

🧠 **VETERAN TAPE READING (The Big Picture)**
A 2-3 sentence plain-English summary of what is happening beneath the surface. Is the market accumulating, distributing, trend-expanding, or trapping breakout traders in a low-volume squeeze?

📊 **LIVE MARKET TAPE & REGIME**
• **Current Price**: [Exact Price & Currency] ([Session Change %])
• **Structural Regime**: [Trend / Consolidation Range / Volatility Squeeze]
• **Multi-Timeframe Alignment**: Summary across 5m, 15m, 1h, and Daily.

🗺️ **TRADINGVIEW CHART BLUEPRINT (Levels to Watch on Your Chart)**
• 🔴 **Overhead Resistance & Supply**: Key resistance level / PDH with exact price.
• 🟢 **Downside Support & Demand**: Key support level / PDL with exact price.
• 🔍 **What to Look For on Your Candles**: Specific candle behavior to watch (e.g. rejection wicks, volume expansion bars).

💧 **SMART MONEY LIQUIDITY MAP (The Traps)**
• **Buy-Side Liquidity (Overhead Stops)**: Where breakout buyers and short-seller stops are resting.
• **Sell-Side Liquidity (Downside Stops)**: Where breakdown sellers and long stops are resting.
• **Recent Stop Sweeps**: Any detected false breaks or stop runs.

📦 **VOLUME, MOMENTUM & VOLATILITY ENGINE**
• **Relative Volume (RVOL)**: Is institutional volume expanding (>1.2x) or is price drifting on retail volume?
• **RSI & Momentum**: Momentum state, bullish/bearish momentum divergence.
• **ATR (Volatility Range)**: Current expected intraday swing bandwidth.

🎯 **SCENARIOS & GAME PLAN**
• 🟢 **The Bullish Case**: Confirmation trigger level, volume required, and upside target pool.
• 🔴 **The Bearish Case**: Breakdown level, institutional selling signs, and downside target pool.
• ⚠️ **Invalidation Line**: The exact price level where the primary thesis is dead wrong.

💡 **100-YEAR VETERAN WISDOM**
A memorable, timeless market principle relevant to this specific situation (e.g., on patience during range chop, honoring stop invalidations, or waiting for liquidity sweeps before acting).

FOR DIRECT SHORT QUESTIONS (e.g., "What is the price of Gold?", "Is NIFTY oversold?"):
Deliver a concise, direct, high-impact veteran answer in 2-3 focused paragraphs with verified numbers, without forcing the entire 7-section template.
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
            "Channel the deep analytical wisdom of a 100-year veteran market researcher. "
            "Deliver an institutional tape-reading breakdown that aligns directly with what the user is seeing on their live TradingView chart. "
            "Ensure the analysis is crystal clear, intuitive, highly structured, and demystifies smart-money liquidity mechanics for immediate practical understanding."
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
