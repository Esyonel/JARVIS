"""
plugins/sos_shield.py — emergency alert.

Sends a real, immediate Telegram message when triggered — reuses the exact
bot-token/chat-id already used by telegram_notify.py, so anyone who already
has that configured gets a working SOS with no extra setup. No GPS exists
on a desktop, so location is "best-effort text the caller supplies", not a
real coordinate lookup.
"""
import time

import requests

from memory.config_manager import load_api_keys

PLUGIN = {
    "name": "sos_shield",
    "description": (
        "Acil durum uyarısı gönderir: yapılandırılmış Telegram botu üzerinden "
        "anında acil durum kişisine/kanalına mesaj iletir. 'acil durum', "
        "'yardım gönder', 'sos' gibi komutlarda kullanılır."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "description": "'trigger' (SOS'u tetikle ve gönder)."
            },
            "location": {
                "type": "STRING",
                "description": "Bilinen konum bilgisi (opsiyonel, serbest metin)."
            },
            "note": {
                "type": "STRING",
                "description": "Duruma dair ek not (opsiyonel)."
            }
        },
        "required": ["action"]
    }
}

_API = "https://api.telegram.org/bot{token}/sendMessage"


def run(parameters: dict, player=None, session_memory=None) -> str:
    action = str(parameters.get("action", "trigger")).strip().lower()
    if action != "trigger":
        return f"Bilinmeyen eylem: {action}"

    keys = load_api_keys()
    token = keys.get("telegram_bot_token")
    chat_id = keys.get("telegram_chat_id")
    if not token or not chat_id:
        return (
            "SOS Shield yapılandırılmamış — config/api_keys.json içine "
            "'telegram_bot_token' ve 'telegram_chat_id' eklemeniz gerekiyor."
        )

    location = str(parameters.get("location", "")).strip()
    note = str(parameters.get("note", "")).strip()
    ts = time.strftime("%Y-%m-%d %H:%M:%S")

    text = f"🚨 ACİL DURUM — {ts}\n"
    if location:
        text += f"Konum: {location}\n"
    if note:
        text += f"Not: {note}\n"
    text += "Bu uyarı JARVIS SOS Shield tarafından otomatik gönderildi."

    try:
        resp = requests.post(_API.format(token=token), json={"chat_id": chat_id, "text": text}, timeout=15)
    except requests.RequestException as e:
        return f"SOS mesajı gönderilemedi: {e}"

    if resp.status_code != 200:
        return f"SOS mesajı gönderilemedi (HTTP {resp.status_code})."

    if player:
        try:
            player.write_log("SEC: SOS Shield tetiklendi — Telegram'a uyarı gönderildi.")
        except Exception:
            pass
    return "Acil durum uyarısı gönderildi."
