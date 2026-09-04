"""
Natural Language Intent Classifier and Tool Router.
Maps questions to analytical categories and identifies minimal required MCP tools.
"""

from __future__ import annotations

import re
from enum import Enum
from typing import Any, Dict, List, Set


class QueryIntent(str, Enum):
    GREETING = "GREETING"
    PRICE_CHECK = "PRICE_CHECK"
    GENERAL_STATUS = "GENERAL_STATUS"
    WHY_DRIVERS = "WHY_DRIVERS"
    LIQUIDITY = "LIQUIDITY"
    STRUCTURE = "STRUCTURE"
    MOMENTUM_VOLUME = "MOMENTUM_VOLUME"
    TIMEFRAME_TREND = "TIMEFRAME_TREND"
    SETUP_CHECK = "SETUP_CHECK"
    MARKET_BRIEFING = "MARKET_BRIEFING"
    COMPARE = "COMPARE"
    WATCHLIST = "WATCHLIST"
    UNKNOWN = "UNKNOWN"


def classify_query_intent(text: str) -> QueryIntent:
    """Classifies user natural language input into a specific analytical intent."""
    t = text.lower().strip()

    # 0. Conversational greetings & introductory assistance
    greetings = {"hello", "hi", "hey", "hola", "namaste", "good morning", "good afternoon", "good evening", "who are you", "what can you do", "help", "start"}
    words = t.split()
    if t in greetings or (words and words[0] in greetings and len(words) <= 3):
        return QueryIntent.GREETING

    # 1. Market briefing / summary
    if any(k in t for k in [
        "market briefing", "summarize today", "summarize market", "what's happening in the market",
        "market overview", "full briefing", "what is happening in the market", "market summary"
    ]):
        return QueryIntent.MARKET_BRIEFING

    # 2. Watchlist
    if any(k in t for k in ["watchlist", "analyze my watchlist", "check watchlist", "show watchlist"]):
        return QueryIntent.WATCHLIST

    # 3. Compare
    if "compare" in t or " vs " in t or " versus " in t:
        return QueryIntent.COMPARE

    # 4. Why / Drivers
    if any(k in t for k in [
        "why is", "why did", "why?", "why", "what's driving", "what is driving",
        "reason for", "cause of", "why falling", "why rising", "why moving"
    ]):
        return QueryIntent.WHY_DRIVERS

    # 5. Liquidity / Support Resistance / Levels / Stops
    if any(k in t for k in [
        "liquidity", "stops", "stop hunt", "sweep", "pdh", "pdl",
        "support", "resistance", "where are the levels", "swing high", "swing low"
    ]):
        return QueryIntent.LIQUIDITY

    # 6. Setup / High quality setup
    if any(k in t for k in [
        "setup", "trade setup", "opportunity", "is there a setup", "any setup",
        "actionable", "trigger", "invalidation"
    ]):
        return QueryIntent.SETUP_CHECK

    # 7. Structure / Trend or range / BOS
    if any(k in t for k in [
        "structure", "market structure", "trend or range", "bos", "choch",
        "breakout", "breakdown", "consolidation", "higher high", "lower low"
    ]):
        return QueryIntent.STRUCTURE

    # 8. Momentum / Volume / Volatility / Indicators
    if any(k in t for k in [
        "momentum", "volume", "rvol", "rsi", "macd", "volatility",
        "atr", "divergence", "what is volume telling", "what is momentum"
    ]):
        return QueryIntent.MOMENTUM_VOLUME

    # 9. Timeframe trend
    if any(k in t for k in [
        "15 minute trend", "15m trend", "1 hour trend", "1h trend", "daily trend",
        "5m trend", "timeframe", "mtf"
    ]):
        return QueryIntent.TIMEFRAME_TREND

    # 10. Simple price check
    if any(k in t for k in ["price of", "current price", "how much is", "what is the price"]):
        return QueryIntent.PRICE_CHECK

    # 11. General instrument query
    return QueryIntent.GENERAL_STATUS


def select_tools_for_intent(
    intent: QueryIntent,
    symbol: str,
    timeframe: str = "15m",
) -> List[Dict[str, Any]]:
    """
    Returns the list of tool calls (tool_name, arguments) strictly needed for the intent.
    Avoids over-fetching while providing all required data.
    """
    tools = []

    if intent == QueryIntent.PRICE_CHECK:
        tools.append({"tool": "get_current_price", "args": {"symbol": symbol}})

    elif intent == QueryIntent.GENERAL_STATUS:
        tools.append({"tool": "get_current_price", "args": {"symbol": symbol}})
        tools.append({"tool": "get_multi_timeframe_analysis", "args": {"symbol": symbol}})
        tools.append({"tool": "get_liquidity_zones", "args": {"symbol": symbol, "timeframe": timeframe}})
        tools.append({"tool": "get_momentum_and_volume", "args": {"symbol": symbol, "timeframe": timeframe}})
        tools.append({"tool": "get_volatility_metrics", "args": {"symbol": symbol, "timeframe": timeframe}})

    elif intent == QueryIntent.WHY_DRIVERS:
        tools.append({"tool": "get_current_price", "args": {"symbol": symbol}})
        tools.append({"tool": "get_market_drivers", "args": {"symbol": symbol}})
        tools.append({"tool": "get_market_breadth", "args": {}})
        tools.append({"tool": "get_macro_overview", "args": {}})
        tools.append({"tool": "get_market_news", "args": {"symbol": symbol}})

    elif intent == QueryIntent.LIQUIDITY:
        tools.append({"tool": "get_current_price", "args": {"symbol": symbol}})
        tools.append({"tool": "get_liquidity_zones", "args": {"symbol": symbol, "timeframe": timeframe}})
        tools.append({"tool": "get_market_structure", "args": {"symbol": symbol, "timeframe": timeframe}})

    elif intent == QueryIntent.STRUCTURE:
        tools.append({"tool": "get_current_price", "args": {"symbol": symbol}})
        tools.append({"tool": "get_market_structure", "args": {"symbol": symbol, "timeframe": timeframe}})
        tools.append({"tool": "get_volatility_metrics", "args": {"symbol": symbol, "timeframe": timeframe}})

    elif intent == QueryIntent.MOMENTUM_VOLUME:
        tools.append({"tool": "get_current_price", "args": {"symbol": symbol}})
        tools.append({"tool": "get_momentum_and_volume", "args": {"symbol": symbol, "timeframe": timeframe}})
        tools.append({"tool": "get_volatility_metrics", "args": {"symbol": symbol, "timeframe": timeframe}})

    elif intent == QueryIntent.TIMEFRAME_TREND:
        tools.append({"tool": "get_current_price", "args": {"symbol": symbol}})
        tools.append({"tool": "get_multi_timeframe_analysis", "args": {"symbol": symbol}})

    elif intent == QueryIntent.SETUP_CHECK:
        tools.append({"tool": "get_current_price", "args": {"symbol": symbol}})
        tools.append({"tool": "get_trading_setup", "args": {"symbol": symbol}})
        tools.append({"tool": "get_tradingview_signals", "args": {"symbol": symbol}})

    elif intent == QueryIntent.MARKET_BRIEFING:
        tools.append({"tool": "get_current_price", "args": {"symbol": "NIFTY"}})
        tools.append({"tool": "get_current_price", "args": {"symbol": "BANKNIFTY"}})
        tools.append({"tool": "get_multi_timeframe_analysis", "args": {"symbol": "NIFTY"}})
        tools.append({"tool": "get_liquidity_zones", "args": {"symbol": "NIFTY", "timeframe": "15m"}})
        tools.append({"tool": "get_market_breadth", "args": {}})
        tools.append({"tool": "get_macro_overview", "args": {}})

    elif intent == QueryIntent.COMPARE:
        tools.append({"tool": "get_current_price", "args": {"symbol": "NIFTY"}})
        tools.append({"tool": "get_current_price", "args": {"symbol": "BANKNIFTY"}})
        tools.append({"tool": "get_market_structure", "args": {"symbol": "NIFTY", "timeframe": "15m"}})
        tools.append({"tool": "get_market_structure", "args": {"symbol": "BANKNIFTY", "timeframe": "15m"}})
        tools.append({"tool": "get_momentum_and_volume", "args": {"symbol": "NIFTY", "timeframe": "15m"}})
        tools.append({"tool": "get_momentum_and_volume", "args": {"symbol": "BANKNIFTY", "timeframe": "15m"}})

    elif intent == QueryIntent.WATCHLIST:
        from config.quant_brain_config import settings
        for sym in settings.watchlist_symbols[:5]:
            tools.append({"tool": "get_current_price", "args": {"symbol": sym}})

    elif intent == QueryIntent.GREETING:
        tools.append({"tool": "get_macro_overview", "args": {}})

    else:
        tools.append({"tool": "get_current_price", "args": {"symbol": symbol}})
        tools.append({"tool": "get_market_structure", "args": {"symbol": symbol, "timeframe": timeframe}})

    return tools
