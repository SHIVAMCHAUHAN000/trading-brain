"""
Production YFinance Market Data Provider.
Connects to live market data for Indian equities/indices (NSE) and global instruments.
Runs blocking calls in thread pools and caches results.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import pandas as pd
import yfinance as yf
import httpx

from config.quant_brain_config import settings
from live_data.instruments import INSTRUMENTS, resolve_symbol
from live_data.freshness import evaluate_data_freshness
from live_data.cache import market_cache
from live_data.provider import MarketDataProvider

logger = logging.getLogger(__name__)


class YFinanceDataProvider(MarketDataProvider):
    """YFinance implementation of MarketDataProvider."""

    def __init__(self) -> None:
        self.provider_name = "yfinance"
        self._headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "Accept": "application/json",
        }

    async def _async_fetch_quote_direct(self, ticker_str: str) -> Dict[str, Any]:
        """Direct HTTP fetch to Yahoo Finance v8 chart API - fast (<200ms) and immune to scraper throttling."""
        try:
            url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker_str}?interval=15m&range=1d"
            async with httpx.AsyncClient(timeout=5.0, follow_redirects=True) as client:
                resp = await client.get(url, headers=self._headers)
                if resp.status_code == 200:
                    payload = resp.json()
                    result = payload.get("chart", {}).get("result")
                    if result and len(result) > 0:
                        meta = result[0].get("meta", {})
                        price = meta.get("regularMarketPrice")
                        prev_close = meta.get("chartPreviousClose") or meta.get("previousClose")
                        day_high = meta.get("regularMarketDayHigh")
                        day_low = meta.get("regularMarketDayLow")
                        volume = meta.get("regularMarketVolume", 0)

                        if price is not None:
                            change = (price - prev_close) if prev_close else 0.0
                            change_pct = (change / prev_close * 100.0) if (prev_close and prev_close > 0) else 0.0
                            return {
                                "price": round(float(price), 2),
                                "prev_close": round(float(prev_close), 2) if prev_close else round(float(price), 2),
                                "change": round(float(change), 2),
                                "change_pct": round(float(change_pct), 2),
                                "open": round(float(meta.get("regularMarketDayLow", price)), 2),
                                "high": round(float(day_high), 2) if day_high else round(float(price), 2),
                                "low": round(float(day_low), 2) if day_low else round(float(price), 2),
                                "volume": int(volume or 0),
                                "timestamp": datetime.now(timezone.utc),
                            }
        except Exception as e:
            logger.debug("Direct v8 quote fetch failed for %s: %s", ticker_str, e)
        return {}

    async def _async_fetch_candles_direct(self, ticker_str: str, interval: str, range_str: str) -> pd.DataFrame:
        """Direct HTTP fetch for candles from Yahoo Finance v8 chart API."""
        try:
            url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker_str}?interval={interval}&range={range_str}"
            async with httpx.AsyncClient(timeout=6.0, follow_redirects=True) as client:
                resp = await client.get(url, headers=self._headers)
                if resp.status_code == 200:
                    payload = resp.json()
                    result = payload.get("chart", {}).get("result")
                    if result and len(result) > 0:
                        res = result[0]
                        timestamps = res.get("timestamp")
                        indicators = res.get("indicators", {}).get("quote", [{}])[0]
                        if timestamps and "close" in indicators and indicators["close"]:
                            df = pd.DataFrame({
                                "open": indicators.get("open"),
                                "high": indicators.get("high"),
                                "low": indicators.get("low"),
                                "close": indicators.get("close"),
                                "volume": indicators.get("volume", [0] * len(timestamps)),
                            }, index=pd.to_datetime(timestamps, unit="s", utc=True))
                            df = df.dropna(subset=["close"])
                            return df
        except Exception as e:
            logger.debug("Direct v8 candles fetch failed for %s: %s", ticker_str, e)
        return pd.DataFrame()

    async def _fetch_spot_gold_quote(self) -> Dict[str, Any]:
        """Fetch real-time spot gold quote matching TradingView TVC:GOLD / XAUUSD."""
        # 1. Try Binance PAXGUSDT (100% physically backed spot gold, sub-100ms)
        try:
            url = "https://api.binance.com/api/v3/ticker/24hr?symbol=PAXGUSDT"
            async with httpx.AsyncClient(timeout=4.0) as client:
                resp = await client.get(url, headers=self._headers)
                if resp.status_code == 200:
                    d = resp.json()
                    price = float(d.get("lastPrice", 0))
                    prev_close = float(d.get("prevClosePrice", price))
                    change = float(d.get("priceChange", price - prev_close))
                    change_pct = float(d.get("priceChangePercent", 0.0))
                    high = float(d.get("highPrice", price))
                    low = float(d.get("lowPrice", price))
                    volume = int(float(d.get("volume", 0)))
                    if price > 0:
                        return {
                            "price": round(price, 2),
                            "prev_close": round(prev_close, 2),
                            "change": round(change, 2),
                            "change_pct": round(change_pct, 2),
                            "open": round(prev_close, 2),
                            "high": round(high, 2),
                            "low": round(low, 2),
                            "volume": volume,
                            "timestamp": datetime.now(timezone.utc),
                        }
        except Exception as e:
            logger.debug("Binance PAXG spot gold quote failed: %s", e)

        # 2. Try api.gold-api.com
        try:
            url = "https://api.gold-api.com/price/XAU"
            async with httpx.AsyncClient(timeout=4.0) as client:
                resp = await client.get(url, headers=self._headers)
                if resp.status_code == 200:
                    d = resp.json()
                    price = float(d.get("price", 0))
                    if price > 0:
                        return {
                            "price": round(price, 2),
                            "prev_close": round(price, 2),
                            "change": 0.0,
                            "change_pct": 0.0,
                            "open": round(price, 2),
                            "high": round(price, 2),
                            "low": round(price, 2),
                            "volume": 0,
                            "timestamp": datetime.now(timezone.utc),
                        }
        except Exception as e:
            logger.debug("Gold-API fetch failed: %s", e)

        return {}

    async def _fetch_spot_gold_candles(self, interval: str = "15m", limit: int = 100) -> pd.DataFrame:
        """Fetch real-time spot gold candles matching TradingView TVC:GOLD."""
        binance_interval_map = {
            "1m": "1m", "5m": "5m", "15m": "15m", "30m": "30m",
            "1h": "1h", "60m": "1h", "1d": "1d", "daily": "1d",
            "1wk": "1w", "weekly": "1w"
        }
        b_interval = binance_interval_map.get(interval, "15m")
        try:
            url = f"https://api.binance.com/api/v3/klines?symbol=PAXGUSDT&interval={b_interval}&limit={limit}"
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(url, headers=self._headers)
                if resp.status_code == 200:
                    raw = resp.json()
                    if raw and isinstance(raw, list):
                        df = pd.DataFrame(raw, columns=[
                            "open_time", "open", "high", "low", "close", "volume",
                            "close_time", "qav", "num_trades", "taker_base_vol", "taker_quote_vol", "ignore"
                        ])
                        df["open_time"] = pd.to_datetime(df["open_time"], unit="ms", utc=True)
                        df = df.set_index("open_time")
                        for col in ["open", "high", "low", "close", "volume"]:
                            df[col] = df[col].astype(float)
                        return df[["open", "high", "low", "close", "volume"]].copy()
        except Exception as e:
            logger.debug("Binance PAXG spot gold candles failed: %s", e)
        return pd.DataFrame()

    def _get_ticker_str(self, symbol: str) -> str:
        canonical = resolve_symbol(symbol) or symbol.upper()
        if canonical in INSTRUMENTS:
            return INSTRUMENTS[canonical].ticker
        # If user passes custom ticker (e.g. AAPL, SBIN.NS)
        return symbol

    def _sync_fetch_candles(self, ticker_str: str, interval: str, period: str) -> pd.DataFrame:
        """Synchronous fetch using yfinance."""
        try:
            ticker = yf.Ticker(ticker_str)
            df = ticker.history(period=period, interval=interval, auto_adjust=True)
            if df.empty:
                return pd.DataFrame()
            # Standardize columns to lower case
            df = df.rename(columns={
                "Open": "open",
                "High": "high",
                "Low": "low",
                "Close": "close",
                "Volume": "volume",
            })
            # Filter standard columns
            cols = [c for c in ["open", "high", "low", "close", "volume"] if c in df.columns]
            df = df[cols].copy()
            df = df.dropna()
            return df
        except Exception as e:
            logger.error("Error fetching candles for %s: %s", ticker_str, e)
            return pd.DataFrame()

    def _sync_fetch_quote(self, ticker_str: str) -> Dict[str, Any]:
        """Synchronous fetch of latest quote metrics."""
        try:
            ticker = yf.Ticker(ticker_str)
            fast = ticker.fast_info
            
            # Fast info extraction
            last_price = getattr(fast, "last_price", None)
            prev_close = getattr(fast, "previous_close", None)
            open_price = getattr(fast, "open", None)
            day_high = getattr(fast, "day_high", None)
            day_low = getattr(fast, "day_low", None)
            volume = getattr(fast, "last_volume", None)

            # If fast_info returned None for price, fall back to 1d history
            last_ts = None
            if last_price is None or prev_close is None:
                hist = ticker.history(period="5d", interval="1d")
                if not hist.empty:
                    last_price = float(hist["Close"].iloc[-1])
                    if len(hist) > 1:
                        prev_close = float(hist["Close"].iloc[-2])
                    else:
                        prev_close = float(hist["Open"].iloc[-1])
                    open_price = float(hist["Open"].iloc[-1])
                    day_high = float(hist["High"].iloc[-1])
                    day_low = float(hist["Low"].iloc[-1])
                    volume = int(hist["Volume"].iloc[-1]) if "Volume" in hist else 0
                    last_ts = hist.index[-1].to_pydatetime()
            else:
                last_ts = datetime.now(timezone.utc)

            change = (last_price - prev_close) if (last_price is not None and prev_close is not None) else 0.0
            change_pct = ((change / prev_close) * 100.0) if (prev_close and prev_close > 0) else 0.0

            return {
                "price": round(float(last_price), 2) if last_price is not None else None,
                "prev_close": round(float(prev_close), 2) if prev_close is not None else None,
                "change": round(float(change), 2),
                "change_pct": round(float(change_pct), 2),
                "open": round(float(open_price), 2) if open_price is not None else None,
                "high": round(float(day_high), 2) if day_high is not None else None,
                "low": round(float(day_low), 2) if day_low is not None else None,
                "volume": int(volume) if volume is not None else 0,
                "timestamp": last_ts or datetime.now(timezone.utc),
            }
        except Exception as e:
            logger.error("Error fetching quote for %s: %s", ticker_str, e)
            return {}

    async def get_quote(self, symbol: str) -> Dict[str, Any]:
        """Fetch quote with caching and freshness check."""
        canonical = resolve_symbol(symbol) or symbol.upper()
        cache_key = f"quote_{canonical}"
        cached = await market_cache.get(cache_key)
        if cached:
            return cached

        ticker_str = self._get_ticker_str(canonical)

        # Handle spot gold specifically to align with TradingView TVC:GOLD / XAUUSD
        if canonical == "GOLD":
            data = await self._fetch_spot_gold_quote()
            if not data or data.get("price") is None:
                data = await self._async_fetch_quote_direct("GC=F")
        else:
            # 1. Try high-speed direct Yahoo Finance v8 API (<200ms, cloud-friendly)
            data = await self._async_fetch_quote_direct(ticker_str)
            if not data or data.get("price") is None:
                # 2. Fall back to yfinance python library
                data = await asyncio.to_thread(self._sync_fetch_quote, ticker_str)

        if not data or data.get("price") is None:
            # Fallback: try fetching 15m candle
            candles = await self.get_candles(canonical, interval="15m", period="2d")
            if not candles.empty:
                last_row = candles.iloc[-1]
                prev_row = candles.iloc[-2] if len(candles) > 1 else last_row
                p = float(last_row["close"])
                pc = float(prev_row["close"])
                chg = p - pc
                chg_pct = (chg / pc * 100.0) if pc > 0 else 0.0
                data = {
                    "price": round(p, 2),
                    "prev_close": round(pc, 2),
                    "change": round(chg, 2),
                    "change_pct": round(chg_pct, 2),
                    "open": round(float(last_row["open"]), 2),
                    "high": round(float(candles["high"].max()), 2),
                    "low": round(float(candles["low"].min()), 2),
                    "volume": int(last_row["volume"]),
                    "timestamp": candles.index[-1].to_pydatetime(),
                }

        meta = INSTRUMENTS.get(canonical)
        currency = meta.currency if meta else "INR"
        name = meta.name if meta else canonical

        ts = data.get("timestamp")
        freshness = evaluate_data_freshness(canonical, ts)

        result = {
            "symbol": canonical,
            "name": name,
            "currency": currency,
            "price": data.get("price"),
            "prev_close": data.get("prev_close"),
            "change": data.get("change", 0.0),
            "change_pct": data.get("change_pct", 0.0),
            "open": data.get("open"),
            "high": data.get("high"),
            "low": data.get("low"),
            "volume": data.get("volume", 0),
            "timestamp": ts.isoformat() if ts else None,
            "freshness": freshness,
            "provider": self.provider_name,
        }

        if data.get("price") is not None:
            await market_cache.set(cache_key, result, settings.DATA_CACHE_TTL_PRICE)
        return result

    async def get_candles(
        self,
        symbol: str,
        interval: str = "15m",
        period: Optional[str] = None,
    ) -> pd.DataFrame:
        """Fetch historical or intraday candles with caching."""
        canonical = resolve_symbol(symbol) or symbol.upper()
        ticker_str = self._get_ticker_str(canonical)

        # Standardize periods for yfinance intervals
        if not period:
            if interval in ("1m", "2m"):
                period = "1d"
            elif interval in ("5m", "15m", "30m"):
                period = "5d"
            elif interval in ("60m", "1h"):
                period = "1mo"
            elif interval in ("1d", "daily"):
                period = "6mo"
                interval = "1d"
            elif interval in ("1wk", "weekly"):
                period = "2y"
                interval = "1wk"
            else:
                period = "5d"

        cache_key = f"candles_{canonical}_{interval}_{period}"
        cached = await market_cache.get(cache_key)
        if cached is not None and isinstance(cached, pd.DataFrame) and not cached.empty:
            return cached

        # Handle spot gold specifically to align with TradingView TVC:GOLD / XAUUSD
        if canonical == "GOLD":
            limit = 100 if interval not in ("1d", "1wk") else 180
            df = await self._fetch_spot_gold_candles(interval=interval, limit=limit)
            if not df.empty:
                ttl = settings.DATA_CACHE_TTL_CANDLES if interval not in ("1d", "1wk") else settings.DATA_CACHE_TTL_DAILY
                await market_cache.set(cache_key, df, ttl)
                return df

        # 1. Try direct v8 API first
        range_str = period
        df = await self._async_fetch_candles_direct(ticker_str, interval, range_str)
        if df.empty:
            # 2. Fall back to yfinance library
            df = await asyncio.to_thread(self._sync_fetch_candles, ticker_str, interval, period)

        ttl = settings.DATA_CACHE_TTL_CANDLES if interval not in ("1d", "1wk") else settings.DATA_CACHE_TTL_DAILY
        if not df.empty:
            await market_cache.set(cache_key, df, ttl)
        return df

    async def get_market_breadth(self) -> Dict[str, Any]:
        """Fetch market breadth of top NIFTY components."""
        cache_key = "market_breadth_nse"
        cached = await market_cache.get(cache_key)
        if cached:
            return cached

        universe = ["RELIANCE", "HDFCBANK", "ICICIBANK", "INFY", "TCS", "NIFTY", "BANKNIFTY"]
        quotes = await asyncio.gather(*[self.get_quote(s) for s in universe], return_exceptions=True)

        advances = 0
        declines = 0
        unchanged = 0
        items = []

        for q in quotes:
            if isinstance(q, dict) and q.get("price") is not None:
                chg = q.get("change_pct", 0.0)
                if chg > 0.05:
                    advances += 1
                elif chg < -0.05:
                    declines += 1
                else:
                    unchanged += 1
                items.append({
                    "symbol": q["symbol"],
                    "price": q["price"],
                    "change_pct": chg,
                })

        total = advances + declines + unchanged
        adv_dec_ratio = round(advances / declines, 2) if declines > 0 else (float(advances) if advances > 0 else 1.0)
        
        if advances > declines * 1.5:
            sentiment = "Bullish Breadth (Broad participation)"
        elif declines > advances * 1.5:
            sentiment = "Bearish Breadth (Heavy selling pressure)"
        else:
            sentiment = "Neutral / Mixed Breadth"

        result = {
            "total_tracked": total,
            "advances": advances,
            "declines": declines,
            "unchanged": unchanged,
            "adv_dec_ratio": adv_dec_ratio,
            "sentiment": sentiment,
            "sample_stocks": items,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        await market_cache.set(cache_key, result, 60)
        return result

    async def get_macro_overview(self) -> Dict[str, Any]:
        """Fetch macro assets overview."""
        cache_key = "macro_overview"
        cached = await market_cache.get(cache_key)
        if cached:
            return cached

        macro_symbols = ["USDINR", "GOLD", "SILVER", "CRUDEOIL", "BTC", "SPX", "INDIAVIX"]
        quotes = await asyncio.gather(*[self.get_quote(s) for s in macro_symbols], return_exceptions=True)

        items = {}
        for s, q in zip(macro_symbols, quotes):
            if isinstance(q, dict) and q.get("price") is not None:
                items[s] = {
                    "price": q["price"],
                    "change_pct": q["change_pct"],
                    "currency": q["currency"],
                }

        result = {
            "macro_assets": items,
            "summary": "Macro indicators updated.",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        await market_cache.set(cache_key, result, 120)
        return result


# Global default provider
market_data_provider: MarketDataProvider = YFinanceDataProvider()
