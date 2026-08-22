"""
JARVIS plugin — one-shot live translation trigger ("çevir").

The voice-lock feature (core/voice_id.py) normally drops any audio that
isn't the enrolled owner's voice, so JARVIS never hears anyone else. Saying
"çevir" needs JARVIS to hear whoever speaks NEXT — the owner or someone else
— so this plugin briefly reopens the gate for a single utterance, then it
closes itself automatically. No persistent "mode" stays on.

The actual translation direction (Russian/Kazakh → Turkish, or Turkish →
Russian) is decided by Gemini based on what language the next utterance
turns out to be in — see the TRANSLATE ON "ÇEVİR" section of
core/prompt.txt.
"""

from core import voice_id

PLUGIN = {
    "name": "translate_now",
    "description": (
        "Call this the instant the user says 'çevir' (or 'translate'), before "
        "responding to anything else. It briefly lets JARVIS hear whoever "
        "speaks next — the user themself, or the person next to them — so "
        "that next utterance can be translated. Do not call this for normal "
        "conversation, only when the trigger word 'çevir'/'translate' is heard."
    ),
    "parameters": {"type": "OBJECT", "properties": {}, "required": []},
}

_WINDOW_SECONDS = 8.0


def run(parameters: dict, player=None, session_memory=None) -> str:
    voice_id.open_gate_briefly(_WINDOW_SECONDS)
    msg = "Dinliyorum."
    _log(msg, player)
    return msg


def _log(message: str, player=None) -> None:
    print(f"[TranslateNow] {message[:200]}")
    if player:
        try:
            player.write_log(f"JARVIS: {message}")
        except Exception:
            pass
