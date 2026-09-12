"""
plugins/sleep_mode.py — night/sleep routine.

Two real, self-contained things: winds down any rooms registered in
smart_home.py's local state, and plays genuine white/pink noise through the
speakers — synthesized on the spot with numpy, no audio asset needed. No
smart-home hub is required for the noise half to work on its own.
"""
import json
import threading
from pathlib import Path

import numpy as np
import sounddevice as sd

_BASE = Path(__file__).resolve().parent.parent / "memory"
_SMART_HOME_FILE = _BASE / "smart_home.json"

PLUGIN = {
    "name": "sleep_mode",
    "description": (
        "Uyku/gece rutinini başlatır: kayıtlı odaların ışıklarını söndürür ve/veya "
        "gerçek zamanlı sentezlenen beyaz/pembe gürültü çalar (harici ses dosyası "
        "gerekmez). Kullanım: 'uyku moduna geç', 'ışıkları kapat ve uyku sesi çal'."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "description": "'activate' (ışıkları söndür), 'white_noise' (gürültü çal), 'stop' (gürültüyü durdur), 'status'."
            },
            "duration_minutes": {
                "type": "NUMBER",
                "description": "'white_noise' için çalma süresi (dakika). Varsayılan 20."
            },
            "noise_type": {
                "type": "STRING",
                "description": "'white' veya 'pink'. Varsayılan 'white'."
            }
        },
        "required": ["action"]
    }
}


def _load_rooms() -> dict:
    if not _SMART_HOME_FILE.exists():
        return {}
    try:
        return json.loads(_SMART_HOME_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_rooms(rooms: dict) -> None:
    _BASE.mkdir(parents=True, exist_ok=True)
    _SMART_HOME_FILE.write_text(json.dumps(rooms, ensure_ascii=False, indent=2), encoding="utf-8")


def _generate_noise(kind: str, seconds: float, samplerate: int = 44100) -> np.ndarray:
    n = int(seconds * samplerate)
    white = np.random.normal(0, 0.2, n).astype(np.float32)
    if kind == "pink":
        # Cheap 1/f approximation: integrate white noise, then renormalize.
        pink = np.cumsum(white)
        pink -= pink.mean()
        peak = float(np.max(np.abs(pink))) or 1.0
        return (pink / peak * 0.2).astype(np.float32)
    return white


def run(parameters: dict, player=None, session_memory=None) -> str:
    action = str(parameters.get("action", "status")).strip().lower()

    if action == "activate":
        rooms = _load_rooms()
        if not rooms:
            return "Kayıtlı akıllı ev odası yok — sadece uyku moduna geçildi, söndürülecek ışık bulunamadı."
        for state in rooms.values():
            state["lights"] = False
        _save_rooms(rooms)
        return f"Uyku modu aktif — {len(rooms)} odanın ışıkları söndürüldü. İyi geceler."

    elif action == "white_noise":
        try:
            minutes = float(parameters.get("duration_minutes", 20) or 20)
        except (TypeError, ValueError):
            minutes = 20.0
        minutes = max(1.0, min(minutes, 120.0))
        kind = "pink" if str(parameters.get("noise_type", "white")).strip().lower() == "pink" else "white"

        def _play():
            audio = _generate_noise(kind, minutes * 60.0)
            sd.play(audio, samplerate=44100)

        threading.Thread(target=_play, daemon=True, name="sleep-noise").start()
        return f"{minutes:.0f} dakika boyunca {kind} gürültü çalınıyor."

    elif action == "stop":
        sd.stop()
        return "Ses durduruldu."

    elif action == "status":
        rooms = _load_rooms()
        lit = sum(1 for r in rooms.values() if r.get("lights"))
        return f"{len(rooms)} kayıtlı oda, {lit} tanesinin ışığı açık."

    return f"Bilinmeyen eylem: {action}"
