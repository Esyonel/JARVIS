"""
Synthesises text into a WAV file using JARVIS's OWN voice.

The live session (main.py) speaks through Gemini's native-audio model with the
"Charon" prebuilt voice, so voice notes use the same model family and the same
voice name — otherwise a "voice message from JARVIS" would arrive in a
noticeably different voice than the one the user just talked to.

Output is 16-bit mono PCM in a RIFF/WAV container, which is the format
Chromium's --use-file-for-fake-audio-capture flag expects (see
actions/whatsapp_voice.py).
"""
from __future__ import annotations

import sys
import wave
from pathlib import Path

# Must match main.py's speech_config voice so notes sound like the live session.
VOICE_NAME = "Charon"
TTS_MODEL = "gemini-2.5-flash-preview-tts"
SAMPLE_RATE = 24_000
SAMPLE_WIDTH = 2  # 16-bit


def _base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent


def _default_output_path() -> Path:
    out = _base_dir() / "uploads" / "voice_notes"
    out.mkdir(parents=True, exist_ok=True)
    return out / "voice_note.wav"


def synthesize(text: str, out_path: Path | str | None = None) -> tuple[Path, float]:
    """Renders `text` to a WAV file in JARVIS's voice.

    Returns (path, duration_seconds). Duration is what the caller needs to know
    how long to hold WhatsApp's record button.
    """
    text = (text or "").strip()
    if not text:
        raise ValueError("Cannot synthesise an empty voice note.")

    from google import genai
    from google.genai import types

    from core.gemini_keys import available_keys

    keys = available_keys()
    if not keys:
        raise RuntimeError("No Gemini API key with remaining quota — cannot synthesise voice.")

    client = genai.Client(api_key=keys[0])
    resp = client.models.generate_content(
        model=TTS_MODEL,
        contents=text,
        config=types.GenerateContentConfig(
            response_modalities=["AUDIO"],
            speech_config=types.SpeechConfig(
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=VOICE_NAME)
                )
            ),
        ),
    )

    part = resp.candidates[0].content.parts[0]
    pcm: bytes = part.inline_data.data
    if not pcm:
        raise RuntimeError("Gemini returned no audio for the voice note.")

    path = Path(out_path) if out_path else _default_output_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(SAMPLE_WIDTH)
        wav.setframerate(SAMPLE_RATE)
        wav.writeframes(pcm)

    duration = len(pcm) / (SAMPLE_RATE * SAMPLE_WIDTH)
    return path, duration
