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
        wake_detector.start()
        return "🎙️ 'Hey Jarvis' uyandırma kelimesi dinleyicisi aktif edildi. Artık 'Hey Jarvis' diyerek asistanı uyandırabilirsiniz."
    elif action == "stop":
        wake_detector.stop()
        return "🛑 Uyandırma dinleyicisi durduruldu."
    elif action == "status":
        st = "Aktif" if wake_detector.is_running else "Kapalı"
        return f"Uyandırma Kelimesi Durumu: {st}"

    return f"Bilinmeyen eylem: {action}"
