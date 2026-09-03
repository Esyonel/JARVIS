"""
JARVIS plugin — pick which microphone and which speakers JARVIS uses.

Backed by core/audio_devices.py, which probes host APIs on Windows/macOS/Linux
so the picker only ever offers devices that actually work at JARVIS's audio
rates (16 kHz in, 24 kHz out) — see that module's docstring for why a raw
`sd.query_devices()` list is unusable on its own (the same microphone shows up
under 4 host APIs, and some "working" endpoints are silent sinks).

The chosen device name is saved to config/api_keys.json (see
memory/config_manager.get_audio_device / save_audio_device, keys
input_device / output_device) and is picked up the next time JARVIS opens the
mic/speaker stream — i.e. on the next reconnect or restart, not mid-conversation.
"""

from core import audio_devices
from memory.config_manager import get_audio_device, save_audio_device

PLUGIN = {
    "name": "audio_device_manager",
    "description": (
        "Lists or changes which microphone (input) and which speakers (output) "
        "JARVIS uses for the live voice session. Use for: 'hangi mikrofonu "
        "kullanıyorsun', 'mikrofonumu değiştir', 'hoparlör seç', 'ses "
        "cihazlarını listele', 'kulaklığa geç', 'list audio devices', "
        "'switch microphone', 'use my headset'. NOT for the general hardware "
        "inventory (that is device_manager) — this one is specifically about "
        "which device JARVIS's own mic/speaker stream opens."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "description": (
                    "'list' (default) — show available input/output devices and "
                    "which one is currently selected. 'set' — select a device, "
                    "requires 'kind' and 'device'. 'reset' — go back to system "
                    "default, requires 'kind'."
                ),
            },
            "kind": {
                "type": "STRING",
                "description": "'input' (microphone) or 'output' (speakers).",
            },
            "device": {
                "type": "STRING",
                "description": (
                    "Device name (or a distinctive substring of it) to select — "
                    "as shown by the 'list' action."
                ),
            },
        },
        "required": [],
    },
}


def _kind_label(kind: str) -> str:
    return "Mikrofon" if kind == "input" else "Hoparlör"


def _list_text() -> str:
    parts = []
    for kind in ("input", "output"):
        names = audio_devices.list_devices(kind)
        saved = get_audio_device(kind) or audio_devices.DEFAULT_LABEL
        parts.append(f"{_kind_label(kind)} (şu an: {saved}):")
        if names:
            parts.extend(f"  - {n}" for n in names)
        else:
            parts.append("  (cihaz listesi henüz hazır değil, birazdan tekrar dene)")
    return "\n".join(parts)


def run(parameters: dict, player=None, session_memory=None) -> str:
    action = (parameters.get("action") or "list").strip().lower()

    try:
        if action == "list":
            result = _list_text()

        elif action == "reset":
            kind = (parameters.get("kind") or "").strip().lower()
            if kind not in ("input", "output"):
                return "Hangisini sıfırlayacağımı belirtmelisin: mikrofon mu, hoparlör mü?"
            save_audio_device(kind, "")
            result = (
                f"{_kind_label(kind)} sistem varsayılanına döndürüldü. "
                f"Değişiklik bir sonraki bağlantıda geçerli olacak."
            )

        elif action == "set":
            kind = (parameters.get("kind") or "").strip().lower()
            wanted = (parameters.get("device") or "").strip()
            if kind not in ("input", "output"):
                return "Hangisini değiştireceğimi belirtmelisin: mikrofon mu, hoparlör mü?"
            if not wanted:
                return f"Hangi cihazı seçeceğimi söylemedin. {_list_text()}"

            names = audio_devices.list_devices(kind)
            match = next((n for n in names if n.lower() == wanted.lower()), None)
            if match is None:
                match = next((n for n in names if wanted.lower() in n.lower()), None)
            if match is None:
                return (
                    f"'{wanted}' adında bir {_kind_label(kind).lower()} bulamadım.\n"
                    + _list_text()
                )

            save_audio_device(kind, match)
            result = (
                f"{_kind_label(kind)} '{match}' olarak ayarlandı. "
                f"Değişiklik bir sonraki bağlantıda geçerli olacak."
            )

        else:
            result = f"Bilinmeyen işlem: '{action}'. list, set veya reset kullan."

    except Exception as e:
        result = f"Efendim, ses cihazları işlenemedi: {e}"

    if player:
        try:
            player.write_log(f"JARVIS: {result[:200]}")
        except Exception:
            pass
    return result[:3000]
