"""
Run this once (with JARVIS closed, so nothing else is using the microphone)
to enroll your voice. After this, JARVIS will only react to speech that
matches your voice — other people talking nearby won't trigger a response.

Usage:  .venv\\Scripts\\python.exe enroll_voice.py
"""

import sys

import numpy as np
import sounddevice as sd

from core import voice_id

SECONDS = 8
SAMPLE_RATE = voice_id.SAMPLE_RATE


def main():
    if voice_id.is_enrolled():
        answer = input("A voice profile already exists. Re-record it? [y/N]: ").strip().lower()
        if answer not in ("y", "yes", "e", "evet"):
            print("Cancelled.")
            return

    print(f"\nSpeak naturally for {SECONDS} seconds after the countdown — read a sentence, "
          f"count numbers, anything. Recording starts now.")
    for i in (3, 2, 1):
        print(i)
        sd.sleep(1000)

    print("Recording...")
    recording = sd.rec(int(SECONDS * SAMPLE_RATE), samplerate=SAMPLE_RATE, channels=1, dtype="int16")
    sd.wait()
    print("Done recording.")

    pcm = recording.tobytes()
    if np.abs(recording).mean() < 50:
        print("That recording was almost silent — check your microphone and try again.")
        sys.exit(1)

    print("Computing voice profile...")
    voice_id.enroll_from_pcm(pcm)
    print(f"\nVoice profile saved. Start JARVIS normally — it will now only "
          f"respond to your voice.\nTo undo this, delete: {voice_id._PROFILE_PATH}")


if __name__ == "__main__":
    main()
