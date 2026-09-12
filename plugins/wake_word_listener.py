"""
JARVIS Plugin: wake_word_listener
Allows enabling/disabling and configuring the 'Hey Jarvis' wake word engine.
"""
from typing import Any, Dict
from core.wake_word import wake_detector

PLUGIN = {
    "name": "wake_word_listener",
    "description": (
        "'Hey Jarvis' veya 'Jarvis' uyandırma kelimesini arka planda dinler. "
        "Asistanı el değmeden sesle uyandırmayı sağlar."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "description": "İşlem: 'start', 'stop', 'status'",
            },
        },
        "required": ["action"],
    },
}


def run(parameters: Dict[str, Any], player=None, session_memory=None) -> str:
    action = str(parameters.get("action", "status")).strip()

    if action == "start":
        if wake_detector.is_running:
            return "🎙️ 'Hey Jarvis' dinleyicisi zaten aktif."
        ok = wake_detector.start()
        if not ok:
            return f"❌ Uyandırma kelimesi başlatılamadı: {wake_detector.load_error}"
        return ("🎙️ 'Hey Jarvis' uyandırma kelimesi dinleyicisi aktif edildi. "
                "Mikrofon kapalıyken 'Hey Jarvis' diyerek onu otomatik açabilirsiniz.")
    elif action == "stop":
        wake_detector.stop()
        return "🛑 Uyandırma dinleyicisi durduruldu."
    elif action == "status":
        if wake_detector.is_running:
            st = "Aktif (mikrofon kapalıyken dinliyor)"
        elif wake_detector.load_error:
            st = f"Kapalı — {wake_detector.load_error}"
        else:
            st = "Kapalı"
        return f"Uyandırma Kelimesi Durumu: {st}"

    return f"Bilinmeyen eylem: {action}"
