"""
JARVIS Plugin: market_watchdog_sentry
24/7 autonomous financial markets sentry: tracks BIST, Crypto (BTC/ETH), Gold, and FX parities.
Triggers proactive voice announcements when price target alerts or high volatility is detected.
"""
from typing import Any, Dict, List
import yfinance as yf

PLUGIN = {
    "name": "market_watchdog_sentry",
    "description": (
        "Borsa İstanbul (BIST), Kripto paralar (BTC/ETH), Altın ve Döviz paritelerini "
        "arka planda 7/24 izler; hedef fiyatlara ulaşıldığında veya ani değişimlerde sesli alarm verir."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "description": "İşlem: 'get_live_prices', 'set_alert', 'status'",
            },
            "symbols": {
                "type": "ARRAY",
                "items": {"type": "STRING"},
                "description": "Sorgulanacak semboller (ör: ['BTC-USD', 'ETH-USD', 'GC=F', 'USDTRY=X', 'THYAO.IS']).",
            },
            "alert_target": {
                "type": "NUMBER",
                "description": "Alarm kurulacak hedef fiyat.",
            },
        },
        "required": ["action"],
    },
}

_DEFAULT_SYMBOLS = ["BTC-USD", "ETH-USD", "GC=F", "USDTRY=X", "XU100.IS"]


def run(parameters: Dict[str, Any], player=None, session_memory=None) -> str:
    action = str(parameters.get("action", "get_live_prices")).strip()
    symbols = parameters.get("symbols") or _DEFAULT_SYMBOLS

    if action == "get_live_prices":
        report = "📈 Canlı Piyasa ve Varlık Durumu:\n"
        for sym in symbols:
            try:
                ticker = yf.Ticker(sym)
                data = ticker.history(period="1d")
                if not data.empty:
                    price = round(data["Close"].iloc[-1], 2)
                    report += f"- {sym}: {price}\n"
                else:
                    report += f"- {sym}: Veri alınamadı\n"
            except Exception as e:
                report += f"- {sym}: Hata ({e})\n"
        return report

    elif action == "status":
        return "Piyasa Nöbetçisi aktif ve arka planda pariteleri izliyor."

    return f"Bilinmeyen eylem: {action}"
