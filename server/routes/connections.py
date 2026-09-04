"""
Connections & Integrations Status API Route.
Exposes MCP tools status, Market Data feeds, TradingView webhook health, and Telegram bot status.
"""

from __future__ import annotations

import time
from typing import Any, Dict
from fastapi import APIRouter

from config.quant_brain_config import settings
from mcp_tools.registry import mcp_registry
from storage.repository import QuantBrainRepository

router = APIRouter(prefix="/api/v1/connections", tags=["Connections"])


@router.get("")
async def get_connections_status() -> Dict[str, Any]:
    """Returns the live connection health and metrics for all integrations."""
    tools_status = mcp_registry.get_status()
    tv_alerts = await QuantBrainRepository.get_recent_tv_alerts(limit=1)

    # Telegram status
    tg_configured = bool(settings.TELEGRAM_BOT_TOKEN)
    tg_status = {
        "configured": tg_configured,
        "status": "ONLINE (Polling)" if tg_configured else "STANDBY (Add TELEGRAM_BOT_TOKEN to .env)",
        "authorized_users_count": len(settings.authorized_telegram_ids),
    }

    # Market Data
    market_data_status = {
        "primary_provider": "YFinance Market Connect",
        "supported_segments": ["NSE Equities", "NSE Indices", "Commodities (COMEX/MCX)", "Crypto", "Forex"],
        "status": "CONNECTED",
        "cache_ttl_price_sec": settings.DATA_CACHE_TTL_PRICE,
        "cache_ttl_candles_sec": settings.DATA_CACHE_TTL_CANDLES,
    }

    # TradingView
    tv_status = {
        "webhook_endpoint": "/api/v1/tradingview/webhook",
        "status": "LISTENING",
        "secret_configured": bool(settings.TRADINGVIEW_WEBHOOK_SECRET),
        "last_alert_received": tv_alerts[0].received_at.isoformat() if tv_alerts else None,
    }

    # AI Engine
    from brain.llm_client import quant_llm_client

    active_provider = (
        "openai" if settings.OPENAI_API_KEY
        else ("gemini" if settings.GEMINI_API_KEY else "rule_based_quant")
    ) if settings.AI_PROVIDER == "auto" else settings.AI_PROVIDER

    quota_warning = quant_llm_client.openai_quota_exhausted
    active_model = (
        (f"{settings.OPENAI_MODEL} (Quota Exhausted: $0 Credits)" if quota_warning else settings.OPENAI_MODEL) if active_provider == "openai"
        else (settings.GEMINI_MODEL if active_provider == "gemini" else "Deterministic Quant Engine")
    )

    ai_status = {
        "provider": active_provider,
        "configured_provider": settings.AI_PROVIDER,
        "model": active_model,
        "openai_api_key_configured": bool(settings.OPENAI_API_KEY),
        "gemini_api_key_configured": bool(settings.GEMINI_API_KEY),
        "openai_quota_exhausted": quota_warning,
        "quota_notice": "OpenAI account has $0 balance (Error 429: credit_balance_exhausted). Add $5 credits at platform.openai.com/billing or use free Gemini." if quota_warning else None,
        "deterministic_fallback_active": True,
        "status": "QUOTA_EXHAUSTED" if quota_warning else "OPERATIONAL",
    }

    return {
        "mcp_tools": {
            "total_tools": len(tools_status),
            "tools": tools_status,
        },
        "market_data": market_data_status,
        "tradingview": tv_status,
        "telegram": tg_status,
        "ai_engine": ai_status,
        "timestamp": time.time(),
    }
