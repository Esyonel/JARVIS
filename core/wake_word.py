"""
core/wake_word.py — local, offline "Hey Jarvis" wake-word detection.

WHY THIS DOES NOT OPEN ITS OWN MICROPHONE
    main.py already keeps one InputStream open for the whole life of a
    session (see JarvisLive._listen_audio) — that raw audio only reaches
    Gemini once the mic is unmuted (ui.muted == False). A second InputStream
    here would either fight the first one for the same device or duplicate
    the whole audio pipeline for a feature that is only useful in the one
    state where nothing is already listening. So this module opens nothing:
    main.py hands it the same int16 PCM chunks via feed() while the mic is
    muted, and it does nothing while unmuted — every word is already going
    straight to Gemini at that point, so there is nothing to "wake".

WHY A WORKER THREAD, NOT INLINE IN THE AUDIO CALLBACK
    feed() is called from PortAudio's realtime callback, which has a hard
    ~64 ms deadline per block (see the comment on TensionMeter in main.py —
    miss it and the driver drops/repeats samples, audible as choppy mic
    input). ONNX inference is light but not free, so feed() only pushes
    bytes onto a bounded queue and returns; a dedicated background thread
    drains it and runs the model at its own pace. If that thread ever falls
    behind, frames are dropped rather than blocking audio capture.

MODEL
    openWakeWord's bundled "hey_jarvis" ONNX model — free, exact phrase
    match for what this assistant is called, runs fully offline once the
    ~1 MB model file is cached locally. Imported lazily inside start()
    because loading onnxruntime costs real time (core/audio_devices.py hit
    the same problem with this exact library — a multi-second import on the
    Qt thread made the settings drawer look broken), which must never
    happen for a feature most sessions never turn on.
"""

from __future__ import annotations

import queue
import threading
import time
from typing import Callable, Optional

import numpy as np

# openWakeWord scores audio in ~80 ms (1280-sample) frames at 16 kHz mono.
_FRAME_SAMPLES = 1280
# openWakeWord's usual 0.5 default never fired in real use on this mic/room
# — genuine "Hey Jarvis" utterances measured here (both in isolation and
# inside the running app) scored 0.17-0.47, while nothing else observed over
# several minutes of normal use scored above 0.1. 0.15 catches real
# utterances with clear headroom over that noise floor.
_DETECT_THRESHOLD = 0.15
_COOLDOWN_SECONDS = 3.0


class WakeWordDetector:
    def __init__(self, wake_callback: Optional[Callable[[], None]] = None):
        self.wake_callback = wake_callback
        self.is_running = False
        self._model = None
        self._queue: "queue.Queue[np.ndarray]" = queue.Queue(maxsize=50)
        self._buf = np.empty(0, dtype=np.int16)
        self._worker: Optional[threading.Thread] = None
        self._last_trigger = 0.0
        self._load_error: Optional[str] = None

    # ── lifecycle ─────────────────────────────────────────────────────────

    def start(self) -> bool:
        """Load the model and start the worker thread. Safe to call from a
        background thread (this is where the slow import happens) and safe
        to call repeatedly — a no-op once already running."""
        if self.is_running:
            return True

        model = self._load_model()
        if model is None:
            return False

        self._model = model
        self._buf = np.empty(0, dtype=np.int16)
        while not self._queue.empty():
            try:
                self._queue.get_nowait()
            except queue.Empty:
                break

        self.is_running = True
        self._load_error = None
        self._worker = threading.Thread(target=self._worker_loop, daemon=True,
                                        name="wake-word")
        self._worker.start()
        print("[WakeWord] 'Hey Jarvis' local model loaded — armed while muted.")
        return True

    def stop(self):
        self.is_running = False
        self._model = None

    @property
    def load_error(self) -> Optional[str]:
        return self._load_error

    def _load_model(self):
        try:
            from openwakeword.model import Model
        except Exception as e:
            self._load_error = (
                f"openwakeword yüklü değil ({e}). "
                f"Kurmak için: pip install openwakeword onnxruntime"
            )
            print(f"[WakeWord] {self._load_error}")
            return None

        try:
            from openwakeword import utils as oww_utils
            oww_utils.download_models(["hey_jarvis"])
        except Exception:
            pass  # already cached locally, or no internet — Model() still
                  # works off whatever is already on disk.

        try:
            return Model(wakeword_models=["hey_jarvis"], inference_framework="onnx")
        except Exception:
            try:
                # Older/newer openwakeword releases name the bundled model
                # differently — fall back to loading every default model and
                # filter by name in _worker_loop instead of failing outright.
                return Model(inference_framework="onnx")
            except Exception as e:
                self._load_error = f"openWakeWord modeli yüklenemedi: {e}"
                print(f"[WakeWord] {self._load_error}")
                return None

    # ── audio path ────────────────────────────────────────────────────────

    def feed(self, pcm_int16: np.ndarray) -> None:
        """Call from the mic callback with each raw int16 chunk while the
        mic is muted. Just a queue push — safe to call from PortAudio's
        realtime thread. No-op unless started."""
        if not self.is_running:
            return
        try:
            self._queue.put_nowait(pcm_int16.reshape(-1).copy())
        except queue.Full:
            pass  # worker is behind — drop rather than risk audio jitter

    def _worker_loop(self):
        while self.is_running:
            try:
                chunk = self._queue.get(timeout=0.5)
            except queue.Empty:
                continue

            self._buf = np.concatenate([self._buf, chunk])
            while len(self._buf) >= _FRAME_SAMPLES:
                frame, self._buf = self._buf[:_FRAME_SAMPLES], self._buf[_FRAME_SAMPLES:]
                self._score_frame(frame)

    def _score_frame(self, frame: np.ndarray) -> None:
        if self._model is None:
            return
        try:
            scores = self._model.predict(frame)
        except Exception as e:
            print(f"[WakeWord] predict() failed: {e}")
            return

        best = 0.0
        for name, score in scores.items():
            if "jarvis" in name.lower() and score > best:
                best = score

        if best >= _DETECT_THRESHOLD:
            now = time.monotonic()
            if now - self._last_trigger >= _COOLDOWN_SECONDS:
                self._last_trigger = now
                self.trigger_wake()

    def trigger_wake(self):
        if self.wake_callback:
            try:
                self.wake_callback()
            except Exception as e:
                print(f"[WakeWord] callback failed: {e}")


wake_detector = WakeWordDetector()
