"""
market_watch/news.py — TL/finans piyasasını etkileyebilecek haber
başlıklarını tarar.

actions/background_monitor.py'nin hash-bazlı "yeni mi?" desenini örnek alır,
ama o modülün aksine kripto/finansı BİLEREK KAPSAR (bu paketin tüm amacı bu)
ve kullanıcı tarafından yapılandırılmaz — sabit bir konu listesini izler.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

_STATE_FILE = Path(__file__).resolve().parent.parent / "memory" / "market_watch_state.json"

TOPICS = [
    "TCMB faiz kararı",
    "FED faiz kararı",
    "Türkiye enflasyon verisi TÜİK",
    "BIST 100 kapanış",
    "dolar tl kur",
]


def _hash(title: str) -> str:
    return hashlib.md5(title.encode("utf-8", errors="ignore")).hexdigest()[:12]


def _load_state() -> dict:
    if _STATE_FILE.exists():
        try:
            return json.loads(_STATE_FILE.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def _save_state(state: dict) -> None:
    _STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    _STATE_FILE.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")


def check_new_headlines() -> list[dict]:
    """Her sabit konu için en güncel başlığı kontrol eder; önceki
    çalıştırmadan farklıysa (yeni haber) listeye ekler. İlk çalıştırmada
    (henüz referans yokken) alarm üretmez, sadece temel durumu kaydeder.

    JARVIS ana sürecinden bağımsız çalışan bu script, JARVIS kök dizinini
    sys.path'e ekler (bkz. monitor.py) — bu sayede actions.web_search
    JARVIS'in geri kalanıyla aynı şekilde import edilebilir."""
    from actions.web_search import _ddg_news

    state = _load_state()
    new_items = []

    for topic in TOPICS:
        try:
            results = _ddg_news(topic, max_results=3)
        except Exception as e:
            print(f"[market_watch.news] ⚠️ '{topic}' aranamadı: {e}")
            continue
        if not results:
            continue

        top = results[0]
        title = (top.get("title") or "").strip()
        if not title:
            continue

        h = _hash(title)
        prev = state.get(topic, {}).get("last_hash")
        state[topic] = {"last_hash": h, "last_title": title}

        if prev is not None and prev != h:
            new_items.append({
                "topic":   topic,
                "title":   title,
                "snippet": (top.get("snippet") or "")[:200],
                "source":  top.get("source", ""),
            })

    _save_state(state)

    if new_items:
        from market_watch.analysis import add_impact_analysis
        add_impact_analysis(new_items)

    return new_items
