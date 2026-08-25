"""
JARVIS plugin — sends a Telegram message via the Bot API, so JARVIS can push
notifications (backend pipeline results, alerts, reminders) to the user's
phone instead of only speaking them.

Setup (one-time, done by the user, not JARVIS):
  1. Talk to @BotFather on Telegram, /newbot, copy the bot token.
  2. Message the new bot once, then open
     https://api.telegram.org/bot<TOKEN>/getUpdates to read your chat_id.
  3. Add to config/api_keys.json:
       "telegram_bot_token": "...",
       "telegram_chat_id": "..."
This file is already in self_improve.py's do-not-touch list, so the token
is never at risk from an autonomous self-edit.
"""

import requests

from memory.config_manager import load_api_keys

PLUGIN = {
    "name": "telegram_notify",
    "description": (
        "Sends a text message to the user's Telegram via the configured bot — "
        "for alerts, reminders, or backend pipeline results the user should see "
        "on their phone even when JARVIS isn't actively listening. Use for: "
        "'bunu telegrama gönder', 'telefonuma bildirim at', 'telegramdan haber "
        "ver'. Requires telegram_bot_token and telegram_chat_id already set in "
        "config/api_keys.json — if missing, this returns setup instructions "
        "instead of sending anything."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "message": {
                "type": "STRING",
                "description": "The text to send.",
            },
        },
        "required": ["message"],
    },
}

_API = "https://api.telegram.org/bot{token}/sendMessage"


def run(parameters: dict, player=None, session_memory=None) -> str:
    message = str(parameters.get("message", "")).strip()
    if not message:
        return "Sir, göndereceğim bir mesaj belirtmedin."

    keys = load_api_keys()
    token = keys.get("telegram_bot_token")
    chat_id = keys.get("telegram_chat_id")
    if not token or not chat_id:
        return (
            "Sir, Telegram henüz yapılandırılmamış. @BotFather ile bir bot "
            "oluşturup token'ı, sonra da chat_id'ni config/api_keys.json "
            "içine 'telegram_bot_token' ve 'telegram_chat_id' olarak eklemen "
            "gerekiyor."
        )

    try:
        resp = requests.post(
            _API.format(token=token),
            json={"chat_id": chat_id, "text": message},
            timeout=15,
        )
    except requests.RequestException as e:
        return f"Sir, Telegram'a ulaşamadım: {e}"

    if resp.status_code != 200:
        detail = ""
        try:
            detail = resp.json().get("description", "")
        except Exception:
            pass
        return f"Sir, Telegram mesajı gönderilemedi ({resp.status_code}): {detail}"

    if player:
        try:
            player.write_log("JARVIS: Telegram mesajı gönderildi.")
        except Exception:
            pass
    return "Mesaj Telegram'a gönderildi."
