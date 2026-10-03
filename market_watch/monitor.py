"""
market_watch/monitor.py — JARVIS'ten BAĞIMSIZ çalışan piyasa/finans izleme
döngüsü.

Değerli maden, döviz ve kripto fiyatlarını + TL'yi etkileyebilecek finans
haberlerini periyodik olarak toplar; Türkçe bir brifing metni üretip
JARVIS/memory/market_briefing.json'a yazar (JARVIS'in ana ekranı bu dosyayı
okur) ve sadece gerçekten yeni bir şey olduğunda (yeni başlık veya ~%1+
fiyat hareketi) ayrı bir Telegram botuna gönderir.

Bağımsız başlatma: watchdog_market_bot.vbs (Borsa_botu/watchdog_telegram_gizli.vbs
ile aynı desen) veya elle:   pythonw.exe -m market_watch.monitor
Tek seferlik test için:      python -m market_watch.monitor --once
"""
from __future__ import annotations

import json
import sys
import time
from datetime import datetime
from pathlib import Path

# ── Force UTF-8 output so emoji/Türkçe print() çağrıları çökmesin ────────────
# cp1254 (Windows Türkçe) birçok Unicode karakteri (⚠️ 🔔 vb.) kodlayamaz —
# main.py'deki aynı düzeltme (bkz. JARVIS/main.py satır ~29-37).
for _stream in (sys.stdout, sys.stderr):
    if _stream is not None and hasattr(_stream, "reconfigure"):
        try:
            _stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

_JARVIS_ROOT = Path(__file__).resolve().parent.parent
if str(_JARVIS_ROOT) not in sys.path:
    sys.path.insert(0, str(_JARVIS_ROOT))

from market_watch.prices import fetch_crypto, fetch_precious_and_fx  # noqa: E402
from market_watch.news import check_new_headlines  # noqa: E402
from market_watch.telegram_push import send_telegram  # noqa: E402

_BRIEFING_FILE     = _JARVIS_ROOT / "memory" / "market_briefing.json"
_PRICE_STATE_FILE  = _JARVIS_ROOT / "memory" / "market_watch_price_state.json"

POLL_SECONDS        = 600   # 10 dakika — "anlık"a yakın, kaynakları zorlamayan bir denge
_MOVE_THRESHOLD_PCT = 1.0   # bu yüzdenin üzerindeki fiyat hareketi "önemli" sayılır


def _load_price_state() -> dict:
    if _PRICE_STATE_FILE.exists():
        try:
            return json.loads(_PRICE_STATE_FILE.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def _save_price_state(state: dict) -> None:
    _PRICE_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    _PRICE_STATE_FILE.write_text(json.dumps(state, indent=2), encoding="utf-8")


def _pct_change(new: float | None, old: float | None) -> float:
    if new is None or old is None or old == 0:
        return 0.0
    return abs(new - old) / abs(old) * 100.0


def _fmt(v, suffix: str = "", digits: int = 2) -> str:
    return f"{v:,.{digits}f}{suffix}" if isinstance(v, (int, float)) else "—"


def _build_summary(fx: dict, crypto: dict, headlines: list[dict]) -> str:
    lines = [f"PİYASA BRİFİNGİ — {datetime.now().strftime('%d.%m.%Y %H:%M')}", ""]

    lines.append("DEĞERLİ MADENLER")
    lines.append(f"  Altın:  {_fmt(fx.get('gold_usd_oz'))} $/ons   |  {_fmt(fx.get('gold_gram_try'))} TL/gram")
    lines.append(f"  Gümüş:  {_fmt(fx.get('silver_usd_oz'))} $/ons   |  {_fmt(fx.get('silver_gram_try'))} TL/gram")
    lines.append("")

    lines.append("DÖVİZ")
    lines.append(f"  USD/TRY: {_fmt(fx.get('usdtry'))}    EUR/TRY: {_fmt(fx.get('eurtry'))}")
    lines.append("")

    lines.append("KRİPTO")
    lines.append(f"  BTC: {_fmt(crypto.get('btc_usd'))} $ ({_fmt(crypto.get('btc_change_pct'), '%')})")
    lines.append(f"  ETH: {_fmt(crypto.get('eth_usd'))} $ ({_fmt(crypto.get('eth_change_pct'), '%')})")

    if headlines:
        lines.append("")
        lines.append("YENİ HABERLER")
        for h in headlines:
            lines.append(f"  • [{h['topic']}] {h['title']}")
            if h.get("snippet"):
                lines.append(f"    {h['snippet']}")
            if h.get("impact"):
                lines.append(f"    ↳ Piyasaya etkisi: {h['impact']}")

    return "\n".join(lines)


def run_once() -> None:
    fx     = fetch_precious_and_fx()
    crypto = fetch_crypto()
    try:
        headlines = check_new_headlines()
    except Exception as e:
        print(f"[market_watch.monitor] ⚠️ Haber taraması başarısız: {e}")
        headlines = []

    prev_prices = _load_price_state()
    combined_now = {**fx, **crypto}
    significant_move = any(
        _pct_change(combined_now.get(k), prev_prices.get(k)) >= _MOVE_THRESHOLD_PCT
        for k in ("gold_usd_oz", "silver_usd_oz", "usdtry", "btc_usd", "eth_usd")
    )

    summary = _build_summary(fx, crypto, headlines)
    is_new  = bool(headlines) or significant_move

    briefing = {
        "updated_at":   datetime.now().isoformat(timespec="seconds"),
        "unread":       is_new,
        "summary_text": summary,
        "prices":       combined_now,
    }
    _BRIEFING_FILE.parent.mkdir(parents=True, exist_ok=True)
    _BRIEFING_FILE.write_text(json.dumps(briefing, indent=2, ensure_ascii=False), encoding="utf-8")

    _save_price_state({
        k: combined_now.get(k)
        for k in ("gold_usd_oz", "silver_usd_oz", "usdtry", "eurtry", "btc_usd", "eth_usd")
    })

    if is_new:
        send_telegram(summary)
        print(f"[market_watch.monitor] 🔔 Yeni içerik ({len(headlines)} haber, "
              f"önemli fiyat hareketi: {significant_move}) — Telegram'a gönderildi.")
    else:
        print("[market_watch.monitor] Güncellendi, yeni bir şey yok.")


def main() -> None:
    if "--once" in sys.argv:
        run_once()
        return
    while True:
        try:
            run_once()
        except Exception as e:
            print(f"[market_watch.monitor] ⚠️ Döngü hatası: {e}")
        time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    main()
