"""
JARVIS plugin — Borsa (BIST) ve Kripto trading botlarinin sanal cuzdan
raporunu ve calisma durumunu OKUR. Botlari baslatma/durdurma yetkisi JARVIS'te
DEGIL — ikisi de Windows Gorev Zamanlayici tarafindan JARVIS'ten bagimsiz
yonetiliyor (Kripto: 7/24 watchdog, Borsa: BIST seans saatlerinde). Bu bilincli
bir tercih: bot yasam donguesu isletim sisteminde, JARVIS'in botlar uzerindeki
yetkisi sadece kod/ozellik ekleme-cikarmayla sinirli.

Iki bot da D:/nu altinda bagimsiz surecler olarak calisir, ayri Telegram
botlarina yazar ve ayri sanal cuzdan tutar. Ikisi de KAGIT UZERINDE islem
yapar - gercek emir gonderilmez, gercek para hareket etmez.

RAPOR SADECE OLGUDUR. Bu plugin cuzdandaki mevcut rakamlari (bakiye, acik
pozisyon, gerceklesen/gerceklesmemis kar-zarar) bildirir. Alim satim tavsiyesi
vermez; kullanici "ne yapayim, alayim mi satayim mi" diye sorarsa dogru cevap
JARVIS'in lisansli yatirim danismani olmadigi ve yalnizca rakamlari
gosterebilecegidir.
"""

import json
import urllib.request
from pathlib import Path

PLUGIN = {
    "name": "trading_bots",
    "description": (
        "Kripto ve Borsa (BIST) trading botlarinin calisma durumunu gosterir ve "
        "sanal cuzdan raporu verir. Kullan: 'kripto botu raporu', 'borsa botu "
        "raporu', 'cuzdanda kar mi zarar mi var', 'botlar calisiyor mu'. "
        "Rapor bakiye, acik pozisyonlar ve kar/zarar rakamlarini OLGU olarak verir - "
        "asla alim satim tavsiyesi degildir. Botlari baslatma/durdurma bu aracin "
        "isi degil — bu Windows Gorev Zamanlayici'da yonetiliyor; kullanici "
        "'botu baslat/durdur' derse Gorev Zamanlayici'ya yonlendir. Belirli bir "
        "hissenin RSI/MACD verisi isteniyorsa bunun yerine bist_market_watch kullan."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "enum": ["durum", "rapor"],
                "description": (
                    "durum = calisiyor mu diye bak (salt-okunur); "
                    "rapor = sanal cuzdan kar/zarar dokumu."
                ),
            },
            "bot": {
                "type": "STRING",
                "enum": ["kripto", "borsa", "hepsi"],
                "description": "Hangi bot. Belirtilmezse 'hepsi' varsayilir.",
            },
        },
        "required": ["action"],
    },
}

_BOTS = {
    "kripto": {
        "label": "Kripto botu",
        "dir": Path("D:/nu/Kripto_botu"),
        "currency": "USDT",
        "prices": "binance",
    },
    "borsa": {
        "label": "Borsa botu",
        "dir": Path("D:/nu/Borsa_botu"),
        "currency": "TL",
        "prices": "yfinance",
    },
}


# --------------------------------------------------------------------------
# Surec gozlemi (salt-okunur — baslatma/durdurma Gorev Zamanlayici'da)
# --------------------------------------------------------------------------

def _find_process(key):
    """Bota ait ana main.py surecini bulur (yoksa None).

    Botun kendi .venv'indeki pythonw.exe ile eslesiyoruz; boylece diger
    Python surecleri ve botun kendi alt surecleri yanlislikla yakalanmaz.
    """
    try:
        import psutil
    except ImportError:
        return None

    folder = _BOTS[key]["dir"].name.lower()
    for proc in psutil.process_iter(["pid", "name", "exe", "cmdline"]):
        try:
            exe = (proc.info.get("exe") or "").lower()
            if folder not in exe:
                continue
            cmdline = " ".join(proc.info.get("cmdline") or []).lower()
            if "main.py" in cmdline:
                return proc
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return None


def _status(key):
    proc = _find_process(key)
    label = _BOTS[key]["label"]
    if not proc:
        return f"{label}: calismiyor."
    paused = (_BOTS[key]["dir"] / "pause.flag").exists()
    try:
        pid = proc.pid
    except Exception:
        pid = "?"
    return f"{label}: {'DURAKLATILMIS' if paused else 'calisiyor'} (PID {pid})."


# --------------------------------------------------------------------------
# Canli fiyatlar
# --------------------------------------------------------------------------

def _binance_prices():
    """Binance'in acik ucundan tum fiyatlari tek istekte ceker: {'FETUSDT': 0.15}."""
    try:
        req = urllib.request.Request(
            "https://api.binance.com/api/v3/ticker/price",
            headers={"User-Agent": "JARVIS/1.0"},
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            rows = json.loads(resp.read().decode("utf-8"))
        return {r["symbol"]: float(r["price"]) for r in rows}
    except Exception:
        return {}


def _yahoo_price(symbol):
    try:
        import yfinance as yf
        hist = yf.Ticker(symbol).history(period="1d")
        if hist is None or hist.empty:
            return None
        return float(hist["Close"].iloc[-1])
    except Exception:
        return None


def _current_price(key, symbol, binance_map):
    if _BOTS[key]["prices"] == "binance":
        return binance_map.get(symbol.replace("/", "").upper())
    return _yahoo_price(symbol)


# --------------------------------------------------------------------------
# Rapor
# --------------------------------------------------------------------------

def _report(key, player=None):
    cfg = _BOTS[key]
    cur = cfg["currency"]
    pf_path = cfg["dir"] / "portfolio.json"

    if not pf_path.exists():
        return f"{cfg['label']}: portfolio.json bulunamadi, rapor cikarilamiyor."

    try:
        data = json.loads(pf_path.read_text(encoding="utf-8"))
    except Exception as e:
        return f"{cfg['label']}: cuzdan dosyasi okunamadi ({e})."

    balance = float(data.get("balance", 0) or 0)
    positions = data.get("positions", {}) or {}
    history = data.get("history", []) or []

    # Gerceklesen K/Z - kapanmis islemlerin toplami, varsayim icermez
    realized = sum(float(h.get("profit", 0) or 0) for h in history)
    wins = sum(1 for h in history if float(h.get("profit", 0) or 0) > 0)
    losses = sum(1 for h in history if float(h.get("profit", 0) or 0) <= 0)

    binance_map = _binance_prices() if (positions and cfg["prices"] == "binance") else {}

    unrealized = 0.0
    market_value = 0.0
    priced, unpriced = 0, 0
    lines = []

    for symbol, p in positions.items():
        # Yeni format 'side', eski kayitlar 'type' kullaniyor
        side = str(p.get("side") or p.get("type") or "Long")
        entry = float(p.get("entry_price", 0) or 0)
        shares = float(p.get("shares", 0) or 0)
        is_long = side.lower() != "short"

        price = _current_price(key, symbol, binance_map)
        if price is None or entry <= 0:
            unpriced += 1
            lines.append(f"  • {symbol} {side} @ {entry:g} — guncel fiyat alinamadi")
            continue

        priced += 1
        pnl = (price - entry) * shares if is_long else (entry - price) * shares
        pct = ((price - entry) / entry * 100) if is_long else ((entry - price) / entry * 100)
        unrealized += pnl
        market_value += price * shares
        lines.append(
            f"  • {symbol} {side} @ {entry:g} → {price:g} | {pnl:+.2f} {cur} ({pct:+.2f}%)"
        )

    total_pnl = realized + unrealized
    verdict = "KARDA" if total_pnl > 0 else ("ZARARDA" if total_pnl < 0 else "BASABAS")

    # Detayli dokum JARVIS loguna - konusulan ozet kisa kalsin
    detail = [
        f"=== {cfg['label']} — sanal cuzdan raporu ===",
        f"Nakit bakiye        : {balance:,.2f} {cur}",
        f"Acik pozisyon       : {len(positions)} adet",
        f"Pozisyon piyasa deg.: {market_value:,.2f} {cur}",
        f"Toplam varlik       : {balance + market_value:,.2f} {cur}",
        f"Gerceklesen K/Z     : {realized:+,.2f} {cur}  ({wins} kazanan / {losses} kaybeden)",
        f"Gerceklesmemis K/Z  : {unrealized:+,.2f} {cur}",
        f"TOPLAM K/Z          : {total_pnl:+,.2f} {cur}  → {verdict}",
    ]
    if lines:
        detail.append("Acik pozisyonlar:")
        detail.extend(lines)
    if unpriced:
        detail.append(f"({unpriced} pozisyonun guncel fiyati alinamadi, K/Z'ye dahil degil)")
    _log("\n".join(detail), player)

    spoken = (
        f"{cfg['label']}: nakit {balance:,.0f} {cur}, {len(positions)} acik pozisyon. "
        f"Gerceklesen {realized:+,.0f}, gerceklesmemis {unrealized:+,.0f}, "
        f"toplam {total_pnl:+,.0f} {cur} — yani {verdict}."
    )
    if unpriced:
        spoken += f" {unpriced} pozisyonun fiyati alinamadi."
    spoken += " Bu sadece cuzdan verisi, yatirim tavsiyesi degil."
    return spoken


def monitor_snapshot() -> dict:
    """Zamanli arka plan izleyicisi (main.py _run_trading_monitor) icin: LLM
    tool-call'i degil, dogrudan cagrilan yardimci. Her bot icin calisma durumu
    + _report() ciktisini dondurur."""
    return {
        key: {"running": _find_process(key) is not None, "report": _report(key)}
        for key in _BOTS
    }


# --------------------------------------------------------------------------

def _log(text, player):
    if player:
        try:
            player.write_log(f"JARVIS: {text}")
        except Exception:
            pass


def _targets(bot):
    bot = (bot or "hepsi").strip().lower()
    if bot in ("hepsi", "both", "all", "ikisi", "tumu", ""):
        return ["kripto", "borsa"]
    if bot in _BOTS:
        return [bot]
    # Serbest metin toleransi: "kripto botu", "borsa botunu" gibi
    for key in _BOTS:
        if key in bot:
            return [key]
    return []


def run(parameters: dict, player=None, session_memory=None) -> str:
    action = str(parameters.get("action", "")).strip().lower()
    targets = _targets(parameters.get("bot"))

    if not targets:
        return "Sir, hangi bottan bahsettigini anlayamadim — kripto mu, borsa mi?"

    if action in ("baslat", "durdur"):
        return (
            "Sir, botları başlatma/durdurma artık benim yetkimde değil — bu "
            "Windows Görev Zamanlayıcı'da otomatik yönetiliyor (Kripto 7/24, "
            "Borsa BIST seans saatlerinde). 'durum' veya 'rapor' sorabilirsiniz."
        )

    handlers = {"durum": _status}

    try:
        if action == "rapor":
            results = [_report(k, player) for k in targets]
        elif action in handlers:
            results = [handlers[action](k) for k in targets]
        else:
            return f"Sir, '{action}' bilinmeyen bir islem. durum veya rapor kullanabilirim."
    except Exception as e:
        return f"Sir, trading_bots calisirken hata verdi: {e}"

    text = " ".join(results)
    if action != "rapor":
        _log(text, player)
    return text
