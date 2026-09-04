"""
Telegram Webhook API Route for Serverless & Cloud Deployments (Vercel, AWS Lambda, Railway).
Allows the Telegram bot to respond immediately to messages without long-polling.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional
from fastapi import APIRouter, Header, HTTPException, Request
try:
    from telegram import Bot, Update
    from telegram.constants import ParseMode
    TELEGRAM_INSTALLED = True
except ImportError:
    Bot = None
    Update = None
    ParseMode = None
    TELEGRAM_INSTALLED = False

from config.quant_brain_config import settings
from brain.orchestrator import quant_brain
from telegram_bot.handlers import is_user_authorized
from telegram_bot.formatter import clean_markdown_for_telegram

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/telegram", tags=["Telegram Webhook"])


@router.post("/webhook")
async def telegram_webhook_handler(request: Request):
    """
    Receives incoming webhook events sent by Telegram servers.
    Works seamlessly on Vercel Serverless functions.
    """
    if not TELEGRAM_INSTALLED:
        raise HTTPException(status_code=503, detail="Telegram dependencies not installed in this environment.")
    if not settings.TELEGRAM_BOT_TOKEN:
        raise HTTPException(status_code=503, detail="Telegram Bot Token not configured in .env.")

    try:
        data = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON payload.")

    bot = Bot(token=settings.TELEGRAM_BOT_TOKEN)
    update = Update.de_json(data, bot)

    if not update or not update.effective_message:
        return {"ok": True, "message": "Ignored non-message update."}

    chat_id = update.effective_chat.id
    user_text = update.effective_message.text or ""

    # Check user authorization
    if not is_user_authorized(update):
        user_id = update.effective_user.id if update.effective_user else "Unknown"
        reject_msg = (
            f"⛔ *Access Restricted*\n\n"
            f"Your Telegram ID `{user_id}` is not authorized to access this personal quant brain.\n"
            f"To authorize your account, add `{user_id}` to `AUTHORIZED_TELEGRAM_USERS` in your `.env` or Vercel Environment Variables."
        )
        try:
            await bot.send_message(chat_id=chat_id, text=reject_msg, parse_mode=ParseMode.MARKDOWN)
        except Exception as e:
            logger.error("Error sending rejection message: %s", e)
        return {"ok": True, "status": "unauthorized_rejected"}

    if not user_text.strip():
        return {"ok": True}

    # Handle commands vs natural language
    cmd = user_text.strip().lower()
    if cmd == "/start":
        reply = (
            "🧠 *Personal Live Quant Brain* online!\n\n"
            "I provide live-market quantitative intelligence, structure, liquidity, momentum, "
            "and multi-timeframe decision support.\n\n"
            "💬 *Ask me any question naturally!* (e.g. *'What is NIFTY doing?'*, *'Why?'*, *'Where is liquidity?'*)"
        )
    elif cmd == "/help":
        reply = (
            "💡 *Sample Questions:*\n"
            "• 'What is NIFTY doing right now?'\n"
            "• 'Why?'\n"
            "• 'Where is liquidity?'\n"
            "• 'What is the 15-minute trend?'\n"
            "• 'What is the price of gold?'\n"
            "• 'Is there a setup developing?'\n"
            "• 'Summarize today's market.'"
        )
    elif cmd in ("/market", "/briefing"):
        res = await quant_brain.process_query(session_id=str(chat_id), user_message="Summarize today's market briefing", channel="telegram")
        reply = res["response"]
    elif cmd == "/nifty":
        res = await quant_brain.process_query(session_id=str(chat_id), user_message="What is NIFTY doing?", channel="telegram")
        reply = res["response"]
    elif cmd == "/banknifty":
        res = await quant_brain.process_query(session_id=str(chat_id), user_message="What is BANKNIFTY doing?", channel="telegram")
        reply = res["response"]
    elif cmd == "/gold":
        res = await quant_brain.process_query(session_id=str(chat_id), user_message="Analyze GOLD", channel="telegram")
        reply = res["response"]
    elif cmd == "/setup":
        res = await quant_brain.process_query(session_id=str(chat_id), user_message="Is there a setup developing?", channel="telegram")
        reply = res["response"]
    else:
        # Full natural language processing
        res = await quant_brain.process_query(session_id=str(chat_id), user_message=user_text, channel="telegram")
        reply = res["response"]

    # Send response back to user via Telegram
    try:
        await bot.send_message(
            chat_id=chat_id,
            text=clean_markdown_for_telegram(reply),
            parse_mode=ParseMode.MARKDOWN,
        )
    except Exception as e:
        logger.error("Error sending Telegram message: %s", e)
        # Fallback without markdown parsing if syntax error occurred
        try:
            await bot.send_message(chat_id=chat_id, text=reply)
        except Exception:
            pass

    return {"ok": True}


@router.post("/setup-webhook")
async def setup_telegram_webhook(webhook_url: str):
    """
    Registers your deployed Vercel domain with Telegram's webhook API.
    Example: webhook_url = 'https://your-project.vercel.app/api/v1/telegram/webhook'
    """
    if not TELEGRAM_INSTALLED:
        raise HTTPException(status_code=503, detail="Telegram dependencies not installed in this environment.")
    if not settings.TELEGRAM_BOT_TOKEN:
        raise HTTPException(status_code=400, detail="TELEGRAM_BOT_TOKEN is not configured.")

    bot = Bot(token=settings.TELEGRAM_BOT_TOKEN)
    endpoint = webhook_url.rstrip("/")
    if not endpoint.endswith("/api/v1/telegram/webhook"):
        endpoint = f"{endpoint}/api/v1/telegram/webhook"

    success = await bot.set_webhook(url=endpoint, drop_pending_updates=True)
    info = await bot.get_webhook_info()
    return {
        "success": success,
        "webhook_url": endpoint,
        "pending_update_count": info.pending_update_count,
        "last_error_message": info.last_error_message,
    }


@router.get("/webhook-info")
async def get_telegram_webhook_info():
    """Checks the currently active webhook configured with Telegram."""
    if not TELEGRAM_INSTALLED:
        return {"configured": False, "message": "Telegram dependencies not installed in this environment."}
    if not settings.TELEGRAM_BOT_TOKEN:
        return {"configured": False, "message": "TELEGRAM_BOT_TOKEN not configured."}

    bot = Bot(token=settings.TELEGRAM_BOT_TOKEN)
    info = await bot.get_webhook_info()
    return {
        "configured": True,
        "url": info.url,
        "has_custom_certificate": info.has_custom_certificate,
        "pending_update_count": info.pending_update_count,
        "last_error_date": info.last_error_date,
        "last_error_message": info.last_error_message,
    }
