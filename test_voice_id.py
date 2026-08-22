"""
Quick check for the enrolled voice profile: records a few seconds of audio
and prints the similarity score against your saved profile, so you can see
exactly whether it's recognizing you (and tune the threshold if not).

Usage:  .venv\\Scripts\\python.exe test_voice_id.py
"""

import numpy as np
import sounddevice as sd

from core import voice_id

SECONDS = 4
SAMPLE_RATE = voice_id.SAMPLE_RATE


def main():
    if not voice_id.is_enrolled():
        print("No voice profile found yet — run enroll_voice.py first.")
        return

    print(f"\nSay something for {SECONDS} seconds after the countdown.")
    for i in (3, 2, 1):
        print(i)
        sd.sleep(1000)

    print("Recording...")
    recording = sd.rec(int(SECONDS * SAMPLE_RATE), samplerate=SAMPLE_RATE, channels=1, dtype="int16")
    sd.wait()
    pcm = recording.tobytes()

    if np.abs(recording).mean() < 50:
        print("That recording was almost silent — check your microphone and try again.")
        return

    profile = np.load(voice_id._PROFILE_PATH)
    wav = voice_id._pcm_to_float(pcm)
    embedding = voice_id._get_encoder().embed_utterance(wav)
    similarity = float(
        np.dot(profile, embedding) / (np.linalg.norm(profile) * np.linalg.norm(embedding) + 1e-9)
    )

    verdict = "MATCH" if similarity >= voice_id.DEFAULT_THRESHOLD else "NO MATCH"
    print(f"\nSimilarity: {similarity:.3f}  (threshold: {voice_id.DEFAULT_THRESHOLD})  ->  {verdict}")
    print("Run this again with someone else talking to see their score for comparison.")


if __name__ == "__main__":
    main()
