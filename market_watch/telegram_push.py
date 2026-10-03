"""
market_watch/telegram_push.py — bu pakete özel, AYRI bir Telegram botuna
tek yönlü (push) mesaj gönderir.

JARVIS'in core/telegram_bridge.py'sindeki çift yönlü köprüden KASITLI olarak
bağımsızdır (kullanıcının ayrı bir bot isteği) ve ağır bir bağımlılık
gerektirmez — sadece requests (zaten JARVIS'in requirements.txt'inde var).
"""
from __future__ import annotations

import requests

from memory.config_manager import load_api_keys

_API_URL = "https://api.telegram.org/bot{token}/sendMessage"


def send_telegram(text: str) -> bool:
    keys    = load_api_keys()
    token   = keys.get("finance_telegram_bot_token")
    chat_id = keys.get("finance_telegram_chat_id")
    if not token or not chat_id:
        print(
            "[market_watch.telegram_push] ⚠️ finance_telegram_bot_token/"
            "finance_telegram_chat_id config/api_keys.json'da ayarlanmamış — atlanıyor."
        )
        return False
    try:
        resp = requests.post(
            _API_URL.format(token=token),
            json={"chat_id": chat_id, "text": text[:4000]},
            timeout=15,
        )
        resp.raise_for_status()
        return True
    except Exception as e:
        print(f"[market_watch.telegram_push] ⚠️ Telegram mesajı gönderilemedi: {e}")
        return False
