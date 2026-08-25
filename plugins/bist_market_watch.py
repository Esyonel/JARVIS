"""
JARVIS plugin — BIST (Borsa Istanbul) price + indicator snapshot via yfinance.

DATA AND INDICATORS ONLY. This plugin never places, suggests, or evaluates a
trade — it reports RSI/MACD values as facts, nothing more. JARVIS must not
turn the output into a buy/sell recommendation; if the user asks "al mı
satayım mı" the correct answer is that JARVIS isn't a licensed advisor and
can only show the numbers.
"""

import pandas as pd

PLUGIN = {
    "name": "bist_market_watch",
    "description": (
        "Fetches recent price data for a Borsa Istanbul (BIST) stock and "
        "reports RSI(14) and MACD(12,26,9) indicator values. Use for: 'THYAO "
        "hissesi ne durumda', 'BIST verisi çek', 'RSI/MACD göster'. Reports "
        "raw indicator values only — never gives a buy/sell recommendation "
        "or financial advice; if asked, JARVIS should say it can only show "
        "the numbers, not advise on trades."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "symbol": {
                "type": "STRING",
                "description": (
                    "BIST ticker, e.g. 'THYAO', 'ASELS', 'GARAN'. The '.IS' "
                    "Yahoo Finance suffix is added automatically if missing."
                ),
            },
            "period": {
                "type": "STRING",
                "description": "History window for the indicator calc, e.g. '1mo', '3mo', '6mo'. Defaults to '3mo'.",
            },
        },
        "required": ["symbol"],
    },
}


def _rsi(close: pd.Series, length: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / length, min_periods=length, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / length, min_periods=length, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, float("nan"))
    return 100 - (100 / (1 + rs))


def _macd(close: pd.Series, fast=12, slow=26, signal=9) -> tuple[pd.Series, pd.Series]:
    ema_fast = close.ewm(span=fast, adjust=False).mean()
    ema_slow = close.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    return macd_line, signal_line


def run(parameters: dict, player=None, session_memory=None) -> str:
    symbol = str(parameters.get("symbol", "")).strip().upper()
    period = str(parameters.get("period") or "3mo").strip()
    if not symbol:
        return "Sir, hangi hisseyi sormak istediğini belirtmedin."

    ticker = symbol if symbol.endswith(".IS") else f"{symbol}.IS"

    try:
        import yfinance as yf
    except ImportError:
        return "Sir, yfinance kütüphanesi kurulu değil. install_library ile kurulabilir."

    try:
        hist = yf.Ticker(ticker).history(period=period)
    except Exception as e:
        return f"Sir, '{ticker}' verisi çekilemedi: {e}"

    if hist.empty or len(hist) < 26:
        return (f"Sir, '{ticker}' için yeterli veri bulamadım (RSI/MACD en az "
                 "~26 günlük veri ister — sembolü veya periyodu kontrol et).")

    close = hist["Close"]
    last_close = float(close.iloc[-1])
    prev_close = float(close.iloc[-2])
    change_pct = (last_close - prev_close) / prev_close * 100

    rsi = _rsi(close).iloc[-1]
    macd_line, signal_line = _macd(close)
    macd_val = macd_line.iloc[-1]
    signal_val = signal_line.iloc[-1]
    macd_state = "boğa (MACD sinyalin üstünde)" if macd_val > signal_val else "ayı (MACD sinyalin altında)"

    if pd.isna(rsi):
        rsi_label = "hesaplanamadı"
    elif rsi >= 70:
        rsi_label = f"{rsi:.1f} (aşırı alım bölgesi)"
    elif rsi <= 30:
        rsi_label = f"{rsi:.1f} (aşırı satım bölgesi)"
    else:
        rsi_label = f"{rsi:.1f} (nötr bölge)"

    if player:
        try:
            player.write_log(f"JARVIS: {ticker} — kapanış {last_close:.2f}, RSI {rsi_label}")
        except Exception:
            pass

    return (
        f"{ticker}: son kapanış {last_close:.2f} TL ({change_pct:+.2f}%). "
        f"RSI(14): {rsi_label}. MACD: {macd_val:.3f}, sinyal: {signal_val:.3f} — {macd_state}. "
        "Bu sadece veri, yatırım tavsiyesi değil."
    )
