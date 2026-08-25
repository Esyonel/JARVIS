"""
JARVIS Plugin: voice_cloner
Allows registering and activating custom cloned voices (e.g. Paul Bettany JARVIS or custom speakers).
"""
from typing import Any, Dict
from core.voice_clone import voice_studio

PLUGIN = {
    "name": "voice_cloner",
    "description": (
        "5-10 saniyelik referans ses dosyasıyla yeni bir konuşma sesi klonlar "
        "ve JARVIS'in konuşma sesi olarak ayarlar."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "description": "İşlem: 'list_voices', 'register_sample', 'status'",
            },
            "voice_name": {
                "type": "STRING",
                "description": "Klonlanacak sesin adı (ör: 'paul_bettany_jarvis').",
            },
            "audio_file": {
                "type": "STRING",
                "description": "Referans ses dosyasının yolu (.wav / .mp3).",
            },
        },
        "required": ["action"],
    },
}


def run(parameters: Dict[str, Any], player=None, session_memory=None) -> str:
    action = str(parameters.get("action", "list_voices")).strip()
    voice_name = str(parameters.get("voice_name", "")).strip()
    audio_file = str(parameters.get("audio_file", "")).strip()

    if action == "list_voices":
        voices = voice_studio.list_cloned_voices()
        if not voices:
            return "Henüz klonlanmış özel bir ses bulunmuyor. Varsayılan EdgeTTS / Kokoro motorları devrede."
        return f"🎙️ Klonlanmış Sesler: {', '.join(voices)}"

    elif action == "register_sample":
        if not voice_name or not audio_file:
            return "Lütfen voice_name ve audio_file parametrelerini girin."
        res = voice_studio.set_reference_audio(voice_name, audio_file)
        if res.get("success"):
            return f"✅ '{voice_name}' sesi başarıyla kaydedildi."
        return f"Ses kaydı başarısız: {res.get('error')}"

    elif action == "status":
        return "Ses Klonlama Stüdyosu hazır."

    return f"Bilinmeyen eylem: {action}"
