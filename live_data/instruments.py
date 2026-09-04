"""
Instrument definitions and ticker mapping for Live Quant Brain.
Supports Indian Equities & Indices (NSE) and Global Assets (Commodities, Crypto, FX, Indices).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional


class MarketSegment(str, Enum):
    NSE_INDEX = "NSE_INDEX"
    NSE_EQUITY = "NSE_EQUITY"
    COMMODITY = "COMMODITY"
    CRYPTO = "CRYPTO"
    FOREX = "FOREX"
    GLOBAL_INDEX = "GLOBAL_INDEX"


@dataclass
class InstrumentMeta:
    symbol: str
    name: str
    ticker: str
    segment: MarketSegment
    currency: str
    exchange: str
    lot_size: int = 1
    tick_size: float = 0.05
    description: str = ""
    is_active: bool = True


INSTRUMENTS: Dict[str, InstrumentMeta] = {
    # Indian Indices
    "NIFTY": InstrumentMeta(
        symbol="NIFTY",
        name="Nifty 50 Index",
        ticker="^NSEI",
        segment=MarketSegment.NSE_INDEX,
        currency="INR",
        exchange="NSE",
        description="Benchmark index representing top 50 Indian companies by market cap",
    ),
    "BANKNIFTY": InstrumentMeta(
        symbol="BANKNIFTY",
        name="Nifty Bank Index",
        ticker="^NSEBANK",
        segment=MarketSegment.NSE_INDEX,
        currency="INR",
        exchange="NSE",
        description="Sectoral index of the most liquid and large-cap Indian banking stocks",
    ),
    "FINNIFTY": InstrumentMeta(
        symbol="FINNIFTY",
        name="Nifty Financial Services Index",
        ticker="NIFTY_FIN_SERVICE.NS",
        segment=MarketSegment.NSE_INDEX,
        currency="INR",
        exchange="NSE",
        description="Index representing Indian banks, financial institutions, and insurance companies",
    ),
    "MIDCPNIFTY": InstrumentMeta(
        symbol="MIDCPNIFTY",
        name="Nifty Midcap Select",
        ticker="NIFTY_MIDCAP_100.NS",
        segment=MarketSegment.NSE_INDEX,
        currency="INR",
        exchange="NSE",
        description="Top mid-cap companies listed on NSE",
    ),

    # Indian Major Equities
    "RELIANCE": InstrumentMeta(
        symbol="RELIANCE",
        name="Reliance Industries Ltd",
        ticker="RELIANCE.NS",
        segment=MarketSegment.NSE_EQUITY,
        currency="INR",
        exchange="NSE",
        description="Conglomerate: energy, petrochemicals, telecommunications, and retail",
    ),
    "HDFCBANK": InstrumentMeta(
        symbol="HDFCBANK",
        name="HDFC Bank Ltd",
        ticker="HDFCBANK.NS",
        segment=MarketSegment.NSE_EQUITY,
        currency="INR",
        exchange="NSE",
        description="Largest private sector bank in India, heavy weightage in NIFTY and BANKNIFTY",
    ),
    "ICICIBANK": InstrumentMeta(
        symbol="ICICIBANK",
        name="ICICI Bank Ltd",
        ticker="ICICIBANK.NS",
        segment=MarketSegment.NSE_EQUITY,
        currency="INR",
        exchange="NSE",
        description="Major private bank in India",
    ),
    "INFY": InstrumentMeta(
        symbol="INFY",
        name="Infosys Ltd",
        ticker="INFY.NS",
        segment=MarketSegment.NSE_EQUITY,
        currency="INR",
        exchange="NSE",
        description="Global leader in next-generation digital services and consulting",
    ),
    "TCS": InstrumentMeta(
        symbol="TCS",
        name="Tata Consultancy Services Ltd",
        ticker="TCS.NS",
        segment=MarketSegment.NSE_EQUITY,
        currency="INR",
        exchange="NSE",
        description="Premier IT services and consulting company",
    ),

    # Commodities & Global
    "GOLD": InstrumentMeta(
        symbol="GOLD",
        name="Spot Gold (USD/oz)",
        ticker="XAU-USD",
        segment=MarketSegment.COMMODITY,
        currency="USD",
        exchange="SPOT",
        description="Spot Gold continuous market in USD per troy ounce (matches TradingView TVC:GOLD / XAUUSD)",
    ),
    "GOLDFUT": InstrumentMeta(
        symbol="GOLDFUT",
        name="Gold Futures (COMEX USD/oz)",
        ticker="GC=F",
        segment=MarketSegment.COMMODITY,
        currency="USD",
        exchange="COMEX",
        description="Gold continuous futures contract (USD per troy ounce)",
    ),
    "SILVER": InstrumentMeta(
        symbol="SILVER",
        name="Silver Futures (COMEX USD/oz)",
        ticker="SI=F",
        segment=MarketSegment.COMMODITY,
        currency="USD",
        exchange="COMEX",
        description="Silver continuous futures contract (USD per troy ounce)",
    ),
    "CRUDEOIL": InstrumentMeta(
        symbol="CRUDEOIL",
        name="Crude Oil WTI (NYMEX USD/bbl)",
        ticker="CL=F",
        segment=MarketSegment.COMMODITY,
        currency="USD",
        exchange="NYMEX",
        description="Light sweet crude oil futures contract (USD per barrel)",
    ),

    # Crypto
    "BTC": InstrumentMeta(
        symbol="BTC",
        name="Bitcoin USD",
        ticker="BTC-USD",
        segment=MarketSegment.CRYPTO,
        currency="USD",
        exchange="CRYPTO",
        description="Leading global cryptocurrency",
    ),

    # Currencies & Macro
    "USDINR": InstrumentMeta(
        symbol="USDINR",
        name="USD to INR Spot",
        ticker="INR=X",
        segment=MarketSegment.FOREX,
        currency="INR",
        exchange="FX",
        description="US Dollar to Indian Rupee exchange rate",
    ),
    "SPX": InstrumentMeta(
        symbol="SPX",
        name="S&P 500 Index",
        ticker="^GSPC",
        segment=MarketSegment.GLOBAL_INDEX,
        currency="USD",
        exchange="US",
        description="Standard & Poor's 500 benchmark index",
    ),
    "INDIAVIX": InstrumentMeta(
        symbol="INDIAVIX",
        name="India Volatility Index",
        ticker="^INDIAVIX",
        segment=MarketSegment.NSE_INDEX,
        currency="INR",
        exchange="NSE",
        description="NSE Volatility Index measuring near term market volatility expectation",
    ),
}

# Aliases mapping for natural language queries
ALIAS_MAP: Dict[str, str] = {
    "NIFTY 50": "NIFTY",
    "NIFTY50": "NIFTY",
    "^NSEI": "NIFTY",
    "BANK NIFTY": "BANKNIFTY",
    "BANKNIFTY": "BANKNIFTY",
    "NIFTYBANK": "BANKNIFTY",
    "^NSEBANK": "BANKNIFTY",
    "FIN NIFTY": "FINNIFTY",
    "FINNIFTY": "FINNIFTY",
    "GOLD": "GOLD",
    "SPOT GOLD": "GOLD",
    "XAU": "GOLD",
    "XAUUSD": "GOLD",
    "XAU/USD": "GOLD",
    "TVC:GOLD": "GOLD",
    "PAXG": "GOLD",
    "GC": "GOLDFUT",
    "GC=F": "GOLDFUT",
    "GOLDFUT": "GOLDFUT",
    "GOLD FUTURES": "GOLDFUT",
    "COMEX GOLD": "GOLDFUT",
    "SILVER": "SILVER",
    "XAG": "SILVER",
    "CRUDE": "CRUDEOIL",
    "CRUDE OIL": "CRUDEOIL",
    "OIL": "CRUDEOIL",
    "BITCOIN": "BTC",
    "BTC-USD": "BTC",
    "BTCUSD": "BTC",
    "USD/INR": "USDINR",
    "USD INR": "USDINR",
    "DOLLAR RUPEE": "USDINR",
    "S&P 500": "SPX",
    "S&P": "SPX",
    "SP500": "SPX",
    "VIX": "INDIAVIX",
    "INDIA VIX": "INDIAVIX",
}


def resolve_symbol(query: str) -> Optional[str]:
    """Resolve user query string to canonical symbol."""
    cleaned = query.strip().upper()
    if cleaned in INSTRUMENTS:
        return cleaned
    if cleaned in ALIAS_MAP:
        return ALIAS_MAP[cleaned]
    for alias, canonical in ALIAS_MAP.items():
        if alias in cleaned:
            return canonical
    for symbol in INSTRUMENTS:
        if symbol in cleaned:
            return symbol
    return None
