"""
JARVIS plugin — live stock market / crypto / gold / currency data, especially
BIST (Turkish stock exchange) and major cryptocurrencies.

Uses Yahoo Finance's public chart endpoint for BIST/gold/FX/world indices, and
Binance's public REST API for crypto (same public market-data endpoints
Kripto_botu uses — no key needed, read-only, nothing here ever places an
order). Reports real numbers only. Never gives buy/sell recommendations or
investment advice; that's a hard boundary, not a style choice.
"""

import threading

import numpy as np
import requests

PLUGIN = {
    "name": "market_data",
    "description": (
        "Reports current stock market, crypto, gold, and currency data — "
        "especially the Turkish stock exchange (BIST) and major "
        "cryptocurrencies — including real technical indicators (RSI, SMA, "
        "MACD, Bollinger Bands) and fundamentals (P/E, market cap, dividend "
        "yield where available) for a specific asset, and screening (scanning "
        "a watchlist for a numeric condition like oversold/overbought RSI or "
        "a Bollinger band breakout). Reports numbers and their textbook "
        "definitions ONLY — NEVER a directional call ('will rise/fall'), "
        "NEVER buy/sell/hold advice. If asked 'should I buy/sell' or 'will it "
        "go up', say that's not something JARVIS can advise on, then still "
        "give the data. Use for: 'borsa nasıl', 'BIST 100 ne durumda', 'altın "
        "kaç para', 'THYAO hissesinin RSI'ı ne', 'THYAO teknik analizi', "
        "'Bitcoin kaç dolar', 'ETH teknik analizi', 'aşırı satım bölgesindeki "
        "hisseler/coinler hangileri', 'dünya borsaları nasıl gidiyor', 'dolar "
        "euro kaç TL'. For a specific asset, pass its bare ticker in 'symbol' "
        "(BIST e.g. 'THYAO', 'GARAN'; crypto e.g. 'BTC', 'ETH', 'SOL') "
        "without any suffix — asset type is auto-detected from the symbol."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "symbol": {
                "type": "STRING",
                "description": (
                    "A specific ticker to look up — BIST stock (e.g. 'THYAO') or crypto "
                    "(e.g. 'BTC', 'ETH'). Returns price plus RSI/SMA/MACD/Bollinger and, "
                    "for stocks, fundamentals. Leave empty for a general market overview or a scan."
                ),
            },
            "category": {
                "type": "STRING",
                "description": (
                    "Which overview to give when no symbol/scan is set: 'bist' (BIST 100), "
                    "'altin' (gold), 'dunya' (world indices), 'doviz' (USD/EUR-TRY), "
                    "'kripto' (BTC/ETH/major coins), or 'hepsi' (all — default)."
                ),
            },
            "scan": {
                "type": "STRING",
                "description": (
                    "Screen a watchlist for a condition instead of a single asset: "
                    "'asiri_satim' (RSI <= 30, oversold), 'asiri_alim' (RSI >= 70, "
                    "overbought), 'bollinger_alt' (price below lower Bollinger band), "
                    "'bollinger_ust' (price above upper Bollinger band). Returns which "
                    "tickers currently meet that numeric condition — no ranking, no advice."
                ),
            },
            "asset_type": {
                "type": "STRING",
                "description": "'bist' or 'kripto' — which watchlist to scan. Defaults to 'bist'.",
            },
        },
        "required": [],
    },
}

_HEADERS = {"User-Agent": "Mozilla/5.0 (JARVIS market_data plugin)"}
_TIMEOUT = 6
_GRAMS_PER_TROY_OZ = 31.1034768

_WORLD_INDICES = [("S&P 500", "^GSPC"), ("Dow Jones", "^DJI"), ("Nasdaq", "^IXIC")]


_CRYPTO_SYMBOLS = {
    "BTC", "ETH", "SOL", "BNB", "XRP", "DOGE", "ADA", "AVAX", "LINK", "DOT",
    "MATIC", "POL", "LTC", "TRX", "SHIB", "NEAR", "ICP", "APT", "ARB", "OP",
    "INJ", "SUI", "ATOM", "FIL", "UNI", "AAVE", "TIA", "PEPE", "WLD", "TAO",
}


def run(parameters: dict, player=None, session_memory=None) -> str:
    symbol = (parameters.get("symbol") or "").strip().upper()
    scan = (parameters.get("scan") or "").strip()
    category = (parameters.get("category") or "hepsi").strip().lower()
    asset_type = (parameters.get("asset_type") or "").strip().lower()

    try:
        if scan:
            result = _crypto_scan(scan) if asset_type in ("kripto", "crypto") else _scan_section(scan)
        elif symbol:
            result = _crypto_analysis(symbol) if symbol in _CRYPTO_SYMBOLS else _stock_analysis(symbol)
        else:
            want_bist   = "hepsi" in category or "bist" in category
            want_gold   = "hepsi" in category or "altin" in category or "altın" in category
            want_world  = "hepsi" in category or "dunya" in category or "dünya" in category
            want_fx     = "hepsi" in category or "doviz" in category or "döviz" in category
            want_crypto = "hepsi" in category or "kripto" in category or "crypto" in category

            parts = []
            if want_bist:
                parts.append(_bist_section())
            if want_crypto:
                parts.append(_crypto_overview_section())
            if want_fx:
                parts.append(_fx_section())
            if want_gold:
                parts.append(_gold_section())
            if want_world:
                parts.append(_world_section())
            result = "\n".join(p for p in parts if p)
    except Exception as e:
        result = f"Sir, market data failed unexpectedly: {e}"

    result = (result or "Sir, I couldn't get any market data right now.")[:3000]
    _log(result, player)
    return result


def _yahoo_quote(symbol: str) -> dict | None:
    try:
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
        r = requests.get(url, headers=_HEADERS, timeout=_TIMEOUT, params={"interval": "1d", "range": "1d"})
        r.raise_for_status()
        meta = r.json()["chart"]["result"][0]["meta"]
        price = meta.get("regularMarketPrice")
        prev = meta.get("previousClose") or meta.get("chartPreviousClose")
        if price is None:
            return None
        change_pct = ((price - prev) / prev * 100) if prev else None
        return {"price": price, "prev": prev, "change_pct": change_pct, "currency": meta.get("currency", "")}
    except Exception as e:
        print(f"[MarketData] {symbol} failed: {e}")
        return None


def _fetch_many(symbols: list[str]) -> dict[str, dict | None]:
    out: dict[str, dict | None] = {}
    lock = threading.Lock()

    def _one(sym: str) -> None:
        q = _yahoo_quote(sym)
        with lock:
            out[sym] = q

    threads = [threading.Thread(target=_one, args=(s,), daemon=True) for s in symbols]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=_TIMEOUT + 1)
    return out


def _fmt_change(q: dict) -> str:
    if q.get("change_pct") is None:
        return ""
    sign = "+" if q["change_pct"] >= 0 else ""
    return f" ({sign}{q['change_pct']:.2f}%)"


def _fetch_history(symbol: str, range_: str = "6mo", interval: str = "1d") -> np.ndarray:
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
    r = requests.get(url, headers=_HEADERS, timeout=_TIMEOUT, params={"interval": interval, "range": range_})
    r.raise_for_status()
    result = r.json()["chart"]["result"][0]
    closes = result["indicators"]["quote"][0]["close"]
    return np.array([c for c in closes if c is not None], dtype=float)


def _rsi(closes: np.ndarray, period: int = 14) -> float | None:
    if len(closes) < period + 1:
        return None
    deltas = np.diff(closes)
    gains = np.where(deltas > 0, deltas, 0.0)
    losses = np.where(deltas < 0, -deltas, 0.0)
    avg_gain = gains[:period].mean()
    avg_loss = losses[:period].mean()
    for i in range(period, len(deltas)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def _sma(closes: np.ndarray, period: int) -> float | None:
    if len(closes) < period:
        return None
    return float(np.mean(closes[-period:]))


def _ema_series(closes: np.ndarray, period: int) -> np.ndarray | None:
    if len(closes) < period:
        return None
    w = 2 / (period + 1)
    out = np.empty_like(closes)
    out[0] = closes[0]
    for i in range(1, len(closes)):
        out[i] = closes[i] * w + out[i - 1] * (1 - w)
    return out


def _macd(closes: np.ndarray) -> tuple[float, float] | tuple[None, None]:
    if len(closes) < 35:
        return None, None
    ema12 = _ema_series(closes, 12)
    ema26 = _ema_series(closes, 26)
    macd_line = ema12[-len(ema26):] - ema26
    signal = _ema_series(macd_line, 9)
    if signal is None:
        return None, None
    return float(macd_line[-1]), float(signal[-1])


def _bollinger(closes: np.ndarray, period: int = 20, num_std: float = 2.0) -> tuple[float, float, float] | None:
    if len(closes) < period:
        return None
    window = closes[-period:]
    mid = float(window.mean())
    std = float(window.std())
    return mid - num_std * std, mid, mid + num_std * std


def _rsi_zone(rsi: float) -> str:
    if rsi >= 70:
        return "aşırı alım bölgesi"
    if rsi <= 30:
        return "aşırı satım bölgesi"
    return "nötr bölge"


def _bollinger_position(price: float, bands: tuple[float, float, float]) -> str:
    lower, _mid, upper = bands
    if price > upper:
        return "üst bandın üzerinde"
    if price < lower:
        return "alt bandın altında"
    return "bantlar arasında"


def _fundamentals(symbol: str) -> dict:
    try:
        url = f"https://query1.finance.yahoo.com/v10/finance/quoteSummary/{symbol}"
        r = requests.get(
            url, headers=_HEADERS, timeout=_TIMEOUT,
            params={"modules": "summaryDetail,defaultKeyStatistics"},
        )
        r.raise_for_status()
        result = r.json()["quoteSummary"]["result"][0]
        summary = result.get("summaryDetail", {}) or {}
        stats = result.get("defaultKeyStatistics", {}) or {}

        def _raw(d: dict, k: str):
            v = d.get(k)
            return v.get("raw") if isinstance(v, dict) else None

        return {
            "pe": _raw(summary, "trailingPE"),
            "market_cap": _raw(summary, "marketCap"),
            "dividend_yield": _raw(summary, "dividendYield"),
            "eps": _raw(stats, "trailingEps"),
        }
    except Exception as e:
        print(f"[MarketData] fundamentals {symbol} failed: {e}")
        return {}


def _stock_analysis(symbol: str) -> str:
    full_symbol = f"{symbol}.IS"
    q = _yahoo_quote(full_symbol)
    if not q:
        return f"Sir, I couldn't find BIST data for '{symbol}'."

    lines = [f"{symbol}: {q['price']:.2f} TL{_fmt_change(q)}"]

    try:
        closes = _fetch_history(full_symbol)
    except Exception as e:
        print(f"[MarketData] history {symbol} failed: {e}")
        closes = np.array([])

    if len(closes) > 30:
        rsi = _rsi(closes)
        if rsi is not None:
            lines.append(f"RSI(14): {rsi:.1f} ({_rsi_zone(rsi)})")

        sma20 = _sma(closes, 20)
        if sma20 is not None:
            lines.append(f"SMA20: {sma20:.2f} TL (fiyat SMA20'nin {'üzerinde' if q['price'] > sma20 else 'altında'})")

        sma50 = _sma(closes, 50)
        if sma50 is not None:
            lines.append(f"SMA50: {sma50:.2f} TL (fiyat SMA50'nin {'üzerinde' if q['price'] > sma50 else 'altında'})")

        macd_line, macd_signal = _macd(closes)
        if macd_line is not None:
            pos = "sinyal çizgisinin üzerinde" if macd_line > macd_signal else "sinyal çizgisinin altında"
            lines.append(f"MACD: {macd_line:.3f}, sinyal: {macd_signal:.3f} ({pos})")

        bands = _bollinger(closes)
        if bands is not None:
            lower, mid, upper = bands
            lines.append(
                f"Bollinger(20,2): alt {lower:.2f} / orta {mid:.2f} / üst {upper:.2f} TL "
                f"— fiyat {_bollinger_position(q['price'], bands)}"
            )

    fund = _fundamentals(full_symbol)
    bits = []
    if fund.get("pe"):
        bits.append(f"F/K {fund['pe']:.1f}")
    if fund.get("eps") is not None:
        bits.append(f"HBK {fund['eps']:.2f}")
    if fund.get("dividend_yield"):
        bits.append(f"temettü verimi %{fund['dividend_yield'] * 100:.1f}")
    if fund.get("market_cap"):
        bits.append(f"piyasa değeri {fund['market_cap'] / 1e9:.1f} milyar TL")
    if bits:
        lines.append("Temel veriler: " + ", ".join(bits) + ".")

    return "\n".join(lines)


_BIST_WATCHLIST = [
    "THYAO", "GARAN", "AKBNK", "ISCTR", "YKBNK", "SISE", "EREGL", "KCHOL",
    "SAHOL", "ASELS", "TUPRS", "BIMAS", "PGSUS", "TCELL", "FROTO", "ARCLK",
    "TOASO", "PETKM", "VESTL", "SASA", "HEKTS", "ENJSA", "TAVHL", "MGROS",
    "KRDMD",
]


def _scan_section(criterion: str) -> str:
    crit = criterion.strip().lower()
    hits: list[tuple[str, float]] = []
    lock = threading.Lock()

    def _check(symbol: str) -> None:
        try:
            closes = _fetch_history(f"{symbol}.IS")
            if len(closes) < 30:
                return
            price = float(closes[-1])

            if any(k in crit for k in ("asiri_satim", "oversold", "satım")):
                rsi = _rsi(closes)
                if rsi is not None and rsi <= 30:
                    with lock:
                        hits.append((symbol, rsi))
            elif any(k in crit for k in ("asiri_alim", "overbought", "alım")):
                rsi = _rsi(closes)
                if rsi is not None and rsi >= 70:
                    with lock:
                        hits.append((symbol, rsi))
            elif any(k in crit for k in ("bollinger_alt", "alt bant")):
                bands = _bollinger(closes)
                if bands is not None and price < bands[0]:
                    with lock:
                        hits.append((symbol, price))
            elif any(k in crit for k in ("bollinger_ust", "bollinger_üst", "üst bant")):
                bands = _bollinger(closes)
                if bands is not None and price > bands[2]:
                    with lock:
                        hits.append((symbol, price))
        except Exception as e:
            print(f"[MarketData] scan {symbol} failed: {e}")

    threads = [threading.Thread(target=_check, args=(s,), daemon=True) for s in _BIST_WATCHLIST]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=_TIMEOUT + 3)

    if not hits:
        return f"'{criterion}' kriterine uyan hisse bulunamadı (taranan {len(_BIST_WATCHLIST)} hisse — sabit bir izleme listesi, tüm BIST değil)."

    lines = [f"'{criterion}' kriterine uyanlar ({len(hits)}/{len(_BIST_WATCHLIST)} taranan hisse):"]
    for sym, val in sorted(hits, key=lambda h: h[0]):
        lines.append(f"- {sym}: {val:.1f}")
    return "\n".join(lines)


# ── Crypto (Binance public API — same source Kripto_botu uses, read-only) ──────

_CRYPTO_WATCHLIST = [
    "BTC", "ETH", "SOL", "BNB", "XRP", "DOGE", "ADA", "AVAX", "LINK", "DOT",
    "TRX", "SHIB", "NEAR", "ICP", "APT", "ARB", "OP", "INJ", "SUI", "TIA",
]


def _binance_ticker(symbol: str) -> dict | None:
    try:
        url = "https://api.binance.com/api/v3/ticker/24hr"
        r = requests.get(url, headers=_HEADERS, timeout=_TIMEOUT, params={"symbol": f"{symbol}USDT"})
        r.raise_for_status()
        d = r.json()
        return {
            "price": float(d["lastPrice"]),
            "change_pct": float(d["priceChangePercent"]),
        }
    except Exception as e:
        print(f"[MarketData] Binance {symbol} failed: {e}")
        return None


def _binance_klines(symbol: str, interval: str = "1d", limit: int = 100) -> np.ndarray:
    url = "https://api.binance.com/api/v3/klines"
    r = requests.get(
        url, headers=_HEADERS, timeout=_TIMEOUT,
        params={"symbol": f"{symbol}USDT", "interval": interval, "limit": limit},
    )
    r.raise_for_status()
    klines = r.json()
    return np.array([float(k[4]) for k in klines])  # index 4 = close price


def _fmt_change_pct(pct: float) -> str:
    sign = "+" if pct >= 0 else ""
    return f" ({sign}{pct:.2f}%)"


def _fmt_price(price: float) -> str:
    """Avoids scientific notation: 2 decimals for normal prices, more for sub-$1 altcoins."""
    if price >= 1:
        return f"{price:,.2f}"
    return f"{price:.6f}"


def _crypto_analysis(symbol: str) -> str:
    q = _binance_ticker(symbol)
    if not q:
        return f"Sir, I couldn't find Binance data for '{symbol}'."

    lines = [f"{symbol}: {_fmt_price(q['price'])} USDT{_fmt_change_pct(q['change_pct'])}"]

    try:
        closes = _binance_klines(symbol)
    except Exception as e:
        print(f"[MarketData] klines {symbol} failed: {e}")
        closes = np.array([])

    if len(closes) > 30:
        rsi = _rsi(closes)
        if rsi is not None:
            lines.append(f"RSI(14): {rsi:.1f} ({_rsi_zone(rsi)})")

        sma20 = _sma(closes, 20)
        if sma20 is not None:
            lines.append(f"SMA20: {_fmt_price(sma20)} USDT (fiyat SMA20'nin {'üzerinde' if q['price'] > sma20 else 'altında'})")

        sma50 = _sma(closes, 50)
        if sma50 is not None:
            lines.append(f"SMA50: {_fmt_price(sma50)} USDT (fiyat SMA50'nin {'üzerinde' if q['price'] > sma50 else 'altında'})")

        macd_line, macd_signal = _macd(closes)
        if macd_line is not None:
            pos = "sinyal çizgisinin üzerinde" if macd_line > macd_signal else "sinyal çizgisinin altında"
            lines.append(f"MACD: {_fmt_price(macd_line)}, sinyal: {_fmt_price(macd_signal)} ({pos})")

        bands = _bollinger(closes)
        if bands is not None:
            lower, mid, upper = bands
            lines.append(
                f"Bollinger(20,2): alt {_fmt_price(lower)} / orta {_fmt_price(mid)} / üst {_fmt_price(upper)} USDT "
                f"— fiyat {_bollinger_position(q['price'], bands)}"
            )

    return "\n".join(lines)


def _crypto_overview_section() -> str:
    quotes = {}
    lock = threading.Lock()

    def _one(sym: str) -> None:
        q = _binance_ticker(sym)
        with lock:
            quotes[sym] = q

    watch = ["BTC", "ETH", "SOL"]
    threads = [threading.Thread(target=_one, args=(s,), daemon=True) for s in watch]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=_TIMEOUT + 1)

    parts = []
    for sym in watch:
        q = quotes.get(sym)
        if q:
            parts.append(f"{sym} {_fmt_price(q['price'])}${_fmt_change_pct(q['change_pct'])}")
    if not parts:
        return "Kripto: şu an alınamadı."
    return "Kripto: " + ", ".join(parts) + "."


def _crypto_scan(criterion: str) -> str:
    crit = criterion.strip().lower()
    hits: list[tuple[str, float]] = []
    lock = threading.Lock()

    def _check(symbol: str) -> None:
        try:
            closes = _binance_klines(symbol)
            if len(closes) < 30:
                return
            price = float(closes[-1])

            if any(k in crit for k in ("asiri_satim", "oversold", "satım")):
                rsi = _rsi(closes)
                if rsi is not None and rsi <= 30:
                    with lock:
                        hits.append((symbol, rsi))
            elif any(k in crit for k in ("asiri_alim", "overbought", "alım")):
                rsi = _rsi(closes)
                if rsi is not None and rsi >= 70:
                    with lock:
                        hits.append((symbol, rsi))
            elif any(k in crit for k in ("bollinger_alt", "alt bant")):
                bands = _bollinger(closes)
                if bands is not None and price < bands[0]:
                    with lock:
                        hits.append((symbol, price))
            elif any(k in crit for k in ("bollinger_ust", "bollinger_üst", "üst bant")):
                bands = _bollinger(closes)
                if bands is not None and price > bands[2]:
                    with lock:
                        hits.append((symbol, price))
        except Exception as e:
            print(f"[MarketData] crypto scan {symbol} failed: {e}")

    threads = [threading.Thread(target=_check, args=(s,), daemon=True) for s in _CRYPTO_WATCHLIST]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=_TIMEOUT + 3)

    if not hits:
        return f"'{criterion}' kriterine uyan coin bulunamadı (taranan {len(_CRYPTO_WATCHLIST)} coin — sabit bir izleme listesi)."

    lines = [f"'{criterion}' kriterine uyanlar ({len(hits)}/{len(_CRYPTO_WATCHLIST)} taranan coin):"]
    for sym, val in sorted(hits, key=lambda h: h[0]):
        lines.append(f"- {sym}: {val:.1f}")
    return "\n".join(lines)


def _bist_section() -> str:
    q = _yahoo_quote("XU100.IS")
    if not q:
        return "BIST 100: şu an alınamadı."
    return f"BIST 100: {q['price']:,.0f}{_fmt_change(q)}"


def _fx_section() -> str:
    quotes = _fetch_many(["TRY=X", "EURTRY=X"])
    usd, eur = quotes.get("TRY=X"), quotes.get("EURTRY=X")
    if not usd and not eur:
        return "Döviz: şu an alınamadı."
    parts = []
    if usd:
        parts.append(f"Dolar {usd['price']:.2f} TL{_fmt_change(usd)}")
    if eur:
        parts.append(f"Euro {eur['price']:.2f} TL{_fmt_change(eur)}")
    return "Döviz: " + ", ".join(parts) + "."


def _gold_section() -> str:
    quotes = _fetch_many(["GC=F", "TRY=X"])
    gold_usd_oz, usdtry = quotes.get("GC=F"), quotes.get("TRY=X")
    if not gold_usd_oz:
        return "Altın: şu an alınamadı."
    line = f"Altın: ons başına {gold_usd_oz['price']:,.0f} dolar{_fmt_change(gold_usd_oz)}"
    if usdtry:
        gram_try = gold_usd_oz["price"] * usdtry["price"] / _GRAMS_PER_TROY_OZ
        line += f", gram altın yaklaşık {gram_try:,.0f} TL"
    return line + "."


def _world_section() -> str:
    symbols = [sym for _, sym in _WORLD_INDICES]
    quotes = _fetch_many(symbols)
    parts = []
    for name, sym in _WORLD_INDICES:
        q = quotes.get(sym)
        if q:
            parts.append(f"{name} {q['price']:,.0f}{_fmt_change(q)}")
    if not parts:
        return "Dünya borsaları: şu an alınamadı."
    return "Dünya borsaları: " + ", ".join(parts) + "."


def _log(message: str, player=None) -> None:
    print(f"[MarketData] {message[:200]}")
    if player:
        try:
            player.write_log(f"JARVIS: {message}")
        except Exception:
            pass
