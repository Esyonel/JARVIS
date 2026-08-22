"""
Lightweight data fetchers for the HUD's scrolling ticker bars (BIST, world
markets, world news). Kept separate from plugins/market_data.py and
plugins/daily_briefing.py (those are hot-reloadable tool files triggered by
voice/text) but uses the same public, key-free sources: Yahoo Finance's
chart endpoint, Binance's public REST API, and Turkish newspaper RSS feeds.

Every function is best-effort and never raises — a source that's down just
contributes nothing to the list, it never breaks the ticker.
"""

import threading
import xml.etree.ElementTree as ET

import requests

_HEADERS = {"User-Agent": "Mozilla/5.0 (JARVIS ticker)"}
_TIMEOUT = 6

_BIST_TICKER_LIST = [
    "THYAO", "GARAN", "AKBNK", "ISCTR", "SISE", "EREGL", "KCHOL", "ASELS",
    "TUPRS", "BIMAS", "TCELL", "FROTO", "ARCLK", "SASA", "PGSUS",
]
_WORLD_INDICES = [("S&P500", "^GSPC"), ("DOW", "^DJI"), ("NASDAQ", "^IXIC"), ("DAX", "^GDAXI")]
_CRYPTO_LIST = ["BTC", "ETH", "SOL", "BNB", "XRP"]

_NEWS_FEEDS = [
    "https://www.hurriyet.com.tr/rss/anasayfa",
    "https://www.ntv.com.tr/gundem.rss",
    "https://www.sabah.com.tr/rss/anasayfa.xml",
]


def _yahoo(symbol: str) -> tuple[float, float] | None:
    try:
        r = requests.get(
            f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}",
            headers=_HEADERS, timeout=_TIMEOUT, params={"interval": "1d", "range": "1d"},
        )
        r.raise_for_status()
        meta = r.json()["chart"]["result"][0]["meta"]
        price = meta.get("regularMarketPrice")
        prev = meta.get("previousClose") or meta.get("chartPreviousClose")
        if price is None:
            return None
        pct = ((price - prev) / prev * 100) if prev else 0.0
        return price, pct
    except Exception:
        return None


def _fmt(price: float, pct: float) -> str:
    sign = "+" if pct >= 0 else ""
    return f"{price:,.2f} ({sign}{pct:.2f}%)"


def fetch_bist_items() -> list[str]:
    items: list[str] = []
    lock = threading.Lock()

    def _one(sym: str) -> None:
        q = _yahoo(f"{sym}.IS")
        if q:
            with lock:
                items.append(f"{sym} {_fmt(*q)}")

    symbols = ["XU100"] + _BIST_TICKER_LIST
    threads = [threading.Thread(target=_one, args=(s,), daemon=True) for s in symbols]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=_TIMEOUT + 1)
    return items


def fetch_world_items() -> list[str]:
    items: list[str] = []
    lock = threading.Lock()

    def _idx(name: str, sym: str) -> None:
        q = _yahoo(sym)
        if q:
            with lock:
                items.append(f"{name} {_fmt(*q)}")

    def _crypto(sym: str) -> None:
        try:
            r = requests.get(
                "https://api.binance.com/api/v3/ticker/24hr",
                headers=_HEADERS, timeout=_TIMEOUT, params={"symbol": f"{sym}USDT"},
            )
            r.raise_for_status()
            d = r.json()
            with lock:
                items.append(f"{sym} {_fmt(float(d['lastPrice']), float(d['priceChangePercent']))}")
        except Exception:
            pass

    threads = [threading.Thread(target=_idx, args=(n, s), daemon=True) for n, s in _WORLD_INDICES]
    threads += [threading.Thread(target=_crypto, args=(s,), daemon=True) for s in _CRYPTO_LIST]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=_TIMEOUT + 1)
    return items


def fetch_news_items(max_per_source: int = 6) -> list[str]:
    items: list[str] = []
    lock = threading.Lock()

    def _one(url: str) -> None:
        try:
            r = requests.get(url, headers=_HEADERS, timeout=_TIMEOUT)
            r.raise_for_status()
            root = ET.fromstring(r.content)
            titles = [
                (t.text or "").strip()
                for t in root.findall(".//item/title")
                if t.text and t.text.strip()
            ][:max_per_source]
            with lock:
                items.extend(titles)
        except Exception:
            pass

    threads = [threading.Thread(target=_one, args=(u,), daemon=True) for u in _NEWS_FEEDS]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=_TIMEOUT + 1)
    return items
