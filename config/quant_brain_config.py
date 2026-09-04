"""
Configuration management for Personal Live Quant Brain.
Loads environment variables with robust defaults and validation.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import List, Optional
from dotenv import load_dotenv
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Base directory of the repository
BASE_DIR = Path(__file__).resolve().parent.parent

# Explicitly load .env with override=True so local keys take priority over stale system envs
env_file_path = BASE_DIR / ".env"
if env_file_path.exists():
    load_dotenv(str(env_file_path), override=True)


class QuantBrainSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # General Environment
    APP_ENV: str = Field(default="development", description="Environment: development, staging, production")
    APP_NAME: str = "Personal Live Quant Brain"
    APP_VERSION: str = "1.0.0"
    HOST: str = Field(default="0.0.0.0", description="Server host")
    PORT: int = Field(default=8000, description="Server port")
    LOG_LEVEL: str = Field(default="INFO", description="Logging level")
    SECRET_KEY: str = Field(default="quant-brain-secret-key-change-in-prod-xyz789", description="App secret key")

    # Database
    DATABASE_URL: str = Field(
        default=f"sqlite+aiosqlite:///{BASE_DIR}/data/quant_brain.db",
        description="Async database connection string",
    )
    SQLITE_PATH: str = Field(
        default=str(BASE_DIR / "data" / "quant_brain.db"),
        description="Path for local SQLite database",
    )

    # AI Reasoning Provider
    AI_PROVIDER: str = Field(
        default="auto",
        description="AI Provider: 'gemini', 'openai', 'rule_based_quant', or 'auto'",
    )
    GEMINI_API_KEY: Optional[str] = Field(default=None, description="Google Gemini API key")
    GEMINI_MODEL: str = Field(default="gemini-3.6-flash", description="Gemini model name")
    OPENAI_API_KEY: Optional[str] = Field(default=None, description="OpenAI API key")
    OPENAI_MODEL: str = Field(default="gpt-4o-mini", description="OpenAI model name")

    # Telegram Bot
    TELEGRAM_BOT_TOKEN: Optional[str] = Field(default=None, description="Telegram Bot token from @BotFather")
    AUTHORIZED_TELEGRAM_USERS: str = Field(
        default="",
        description="Comma-separated list of authorized Telegram user IDs or usernames (empty allows all in dev)",
    )

    # TradingView Integration
    TRADINGVIEW_WEBHOOK_SECRET: str = Field(
        default="tv_secret_webhook_pass_123",
        description="Secret key to validate TradingView alert webhooks",
    )

    # Market Data & Freshness
    DATA_CACHE_TTL_PRICE: int = Field(default=15, description="TTL in seconds for live prices")
    DATA_CACHE_TTL_CANDLES: int = Field(default=60, description="TTL in seconds for intraday candles")
    DATA_CACHE_TTL_DAILY: int = Field(default=300, description="TTL in seconds for daily candles")
    MAX_STALE_MINUTES: int = Field(default=20, description="Threshold in minutes before data is marked stale")

    # Watchlist
    DEFAULT_WATCHLIST: str = Field(
        default="NIFTY,BANKNIFTY,GOLD,SILVER,CRUDEOIL,BTC,RELIANCE,HDFCBANK",
        description="Comma-separated default watchlist",
    )

    @property
    def authorized_telegram_ids(self) -> List[str]:
        if not self.AUTHORIZED_TELEGRAM_USERS:
            return []
        return [uid.strip() for uid in self.AUTHORIZED_TELEGRAM_USERS.split(",") if uid.strip()]

    @property
    def watchlist_symbols(self) -> List[str]:
        return [s.strip().upper() for s in self.DEFAULT_WATCHLIST.split(",") if s.strip()]


# Global singleton settings
settings = QuantBrainSettings()
