"""
Local speaker verification — lets JARVIS ignore voices that aren't its
enrolled owner, so background chatter / other people in the room don't
trigger a response.

Uses Resemblyzer (small pretrained speaker-embedding model, CPU-only,
~17 MB, downloaded once on first use) to turn a few seconds of audio into a
256-dim voice embedding, and compares it against the embedding saved during
enrollment via cosine similarity. Runs entirely offline — no audio ever
leaves the machine for this check, separate from whatever gets streamed to
Gemini once it passes.

If nobody has enrolled yet (no config/voice_id.npy), every check passes —
JARVIS behaves exactly as before until the owner enrolls their voice.
"""

from pathlib import Path

import numpy as np

_PROFILE_PATH = Path(__file__).resolve().parent.parent / "config" / "voice_id.npy"
SAMPLE_RATE = 16000  # must match main.py's SEND_SAMPLE_RATE — resemblyzer expects 16 kHz
DEFAULT_THRESHOLD = 0.70
MIN_ENROLL_SECONDS = 5

_encoder = None  # lazy singleton — the model loads once, on first real use
_gate_open_until = 0.0  # monotonic deadline — e.g. "çevir" briefly lets the next speaker through


def open_gate_briefly(seconds: float = 8.0) -> None:
    """Let ANY voice through for the next `seconds` (e.g. one translated utterance)."""
    global _gate_open_until
    import time
    _gate_open_until = time.monotonic() + seconds


def is_gate_disabled() -> bool:
    import time
    return time.monotonic() < _gate_open_until


def _get_encoder():
    global _encoder
    if _encoder is None:
        from resemblyzer import VoiceEncoder
        _encoder = VoiceEncoder()
    return _encoder


def is_enrolled() -> bool:
    return _PROFILE_PATH.exists()


def delete_profile() -> None:
    _PROFILE_PATH.unlink(missing_ok=True)


def enroll_from_pcm(int16_pcm: bytes) -> None:
    """Compute and save the owner's voice embedding from raw 16 kHz mono int16 PCM."""
    wav = _pcm_to_float(int16_pcm)
    embedding = _get_encoder().embed_utterance(wav)
    _PROFILE_PATH.parent.mkdir(parents=True, exist_ok=True)
    np.save(_PROFILE_PATH, embedding)


def matches_owner(int16_pcm: bytes, threshold: float = DEFAULT_THRESHOLD) -> bool:
    """True if the given audio's voice matches the enrolled owner.

    Also True (fail-open) if nobody is enrolled yet, or if the check itself
    errors out — a broken voice check should never make JARVIS go deaf.
    """
    if not is_enrolled():
        return True
    try:
        profile = np.load(_PROFILE_PATH)
        wav = _pcm_to_float(int16_pcm)
        embedding = _get_encoder().embed_utterance(wav)
        similarity = float(
            np.dot(profile, embedding)
            / (np.linalg.norm(profile) * np.linalg.norm(embedding) + 1e-9)
        )
        return similarity >= threshold
    except Exception as e:
        print(f"[VoiceID] check failed, letting audio through: {e}")
        return True


def _pcm_to_float(int16_pcm: bytes) -> np.ndarray:
    return np.frombuffer(int16_pcm, dtype=np.int16).astype(np.float32) / 32768.0
