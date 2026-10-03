"""
market_watch/prices.py — değerli maden, döviz ve kripto fiyatlarını çeker.

Yeni bir bağımlılık (yfinance/ccxt) eklemez: core/ticker_data.py'nin JARVIS
HUD'undaki kayan ticker şeridi için zaten kullandığı, anahtar gerektirmeyen
kaynakları (Yahoo Finance chart endpoint, Binance public REST) yeniden
kullanır.
"""
from __future__ import annotations

import requests

from core.ticker_data import _HEADERS, _TIMEOUT, _yahoo

_OZ_TO_GRAM = 31.1034768

_YAHOO_SYMBOLS = {
    "gold_usd_oz":   "GC=F",
    "silver_usd_oz": "SI=F",
    "usdtry":        "USDTRY=X",
    "eurtry":        "EURTRY=X",
}


def fetch_precious_and_fx() -> dict:
    """Altın/gümüş (USD/ons + TL/gram) ve USDTRY/EURTRY. Kaynak erişilemezse
    ilgili alan None döner — hiçbir zaman istisna fırlatmaz."""
    out: dict[str, float | None] = {}
    for key, symbol in _YAHOO_SYMBOLS.items():
        q = _yahoo(symbol)
        out[key] = q[0] if q else None

    usdtry = out.get("usdtry")
    out["gold_gram_try"] = (
        out["gold_usd_oz"] / _OZ_TO_GRAM * usdtry
        if out.get("gold_usd_oz") and usdtry else None
    )
    out["silver_gram_try"] = (
        out["silver_usd_oz"] / _OZ_TO_GRAM * usdtry
        if out.get("silver_usd_oz") and usdtry else None
    )
    return out


def fetch_crypto() -> dict:
    """BTC/ETH son fiyat + 24s yüzde değişim — core/ticker_data.py ile aynı
    anahtarsız Binance public REST endpoint'i kullanır."""
    out: dict[str, float | None] = {}
    for symbol, key in (("BTC", "btc"), ("ETH", "eth")):
        try:
            r = requests.get(
                "https://api.binance.com/api/v3/ticker/24hr",
                headers=_HEADERS, timeout=_TIMEOUT, params={"symbol": f"{symbol}USDT"},
            )
            r.raise_for_status()
            d = r.json()
            out[f"{key}_usd"] = float(d["lastPrice"])
            out[f"{key}_change_pct"] = float(d["priceChangePercent"])
        except Exception as e:
            print(f"[market_watch.prices] ⚠️ {symbol} alınamadı: {e}")
            out[f"{key}_usd"] = None
            out[f"{key}_change_pct"] = None
    return out
