"""
JARVIS plugin — generates a binaural-beat WAV file: two pure tones, one per
ear, offset by the target beat frequency (the "beat" is perceived by the
brain, not present in either channel alone). Needs stereo headphones to work.

Pure numpy + the stdlib `wave` module — no extra dependency.
"""

import wave
from pathlib import Path

import numpy as np

PLUGIN = {
    "name": "binaural_audio",
    "description": (
        "Generates a binaural-beat audio file (stereo WAV) for focus, "
        "relaxation, meditation, or sleep — e.g. 'odaklanma için ses üret', "
        "'432 hz binaural ses oluştur', 'uyku için delta dalgası çal'. "
        "Requires headphones — the effect needs each ear to hear a slightly "
        "different tone."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "preset": {
                "type": "STRING",
                "description": (
                    "One of: 'odaklanma' (beta, ~18 Hz beat), 'sakin_odak' "
                    "(alpha, ~10 Hz), 'meditasyon' (theta, ~6 Hz), 'uyku' "
                    "(delta, ~2 Hz). Ignored if beat_freq is given directly."
                ),
            },
            "base_freq": {
                "type": "NUMBER",
                "description": "Carrier tone in Hz, e.g. 200 or 432. Defaults to 200.",
            },
            "beat_freq": {
                "type": "NUMBER",
                "description": "Exact beat frequency in Hz — overrides preset if given.",
            },
            "duration_seconds": {
                "type": "NUMBER",
                "description": "Length of the generated audio in seconds. Defaults to 300 (5 minutes).",
            },
            "output_path": {
                "type": "STRING",
                "description": "Where to save the WAV file. Defaults to a file in the user's Music folder.",
            },
        },
        "required": [],
    },
}

_PRESETS = {
    "odaklanma": 18.0,   # beta
    "sakin_odak": 10.0,  # alpha
    "meditasyon": 6.0,   # theta
    "uyku": 2.0,          # delta
}
_SAMPLE_RATE = 44100
_MAX_DURATION = 3600  # 1 hour hard cap


def run(parameters: dict, player=None, session_memory=None) -> str:
    preset = str(parameters.get("preset") or "").strip().lower()
    base_freq = float(parameters.get("base_freq") or 200.0)
    beat_freq = parameters.get("beat_freq")
    duration = float(parameters.get("duration_seconds") or 300.0)
    output_path = str(parameters.get("output_path") or "").strip()

    if beat_freq is not None:
        beat_freq = float(beat_freq)
    elif preset in _PRESETS:
        beat_freq = _PRESETS[preset]
    else:
        beat_freq = _PRESETS["sakin_odak"]

    if not (0.5 <= beat_freq <= 40):
        return "Sir, beat frekansı 0.5-40 Hz aralığında olmalı (binaural etki bu aralıkta çalışır)."
    if not (50 <= base_freq <= 1000):
        return "Sir, taşıyıcı frekans 50-1000 Hz aralığında olmalı."
    duration = max(5.0, min(duration, _MAX_DURATION))

    t = np.linspace(0, duration, int(_SAMPLE_RATE * duration), endpoint=False)
    left = np.sin(2 * np.pi * base_freq * t)
    right = np.sin(2 * np.pi * (base_freq + beat_freq) * t)

    fade_samples = min(int(_SAMPLE_RATE * 2), len(t) // 4)
    if fade_samples > 0:
        fade = np.linspace(0, 1, fade_samples)
        for ch in (left, right):
            ch[:fade_samples] *= fade
            ch[-fade_samples:] *= fade[::-1]

    stereo = np.empty((len(t), 2), dtype=np.int16)
    stereo[:, 0] = np.int16(left * 0.4 * 32767)
    stereo[:, 1] = np.int16(right * 0.4 * 32767)

    if output_path:
        dest = Path(output_path).expanduser()
    else:
        dest = Path.home() / "Music" / f"binaural_{base_freq:.0f}hz_{beat_freq:.1f}hz.wav"

    try:
        dest.parent.mkdir(parents=True, exist_ok=True)
        with wave.open(str(dest), "wb") as wf:
            wf.setnchannels(2)
            wf.setsampwidth(2)
            wf.setframerate(_SAMPLE_RATE)
            wf.writeframes(stereo.tobytes())
    except Exception as e:
        return f"Sir, ses dosyası oluşturulamadı: {e}"

    if player:
        try:
            player.write_log(f"JARVIS: Binaural ses '{dest}' konumuna kaydedildi.")
        except Exception:
            pass
    return (f"{duration:.0f} saniyelik {base_freq:.0f} Hz taşıyıcı / {beat_freq:.1f} Hz beat "
            f"binaural ses '{dest}' konumuna kaydedildi. Kulaklıkla dinlenmeli.")
