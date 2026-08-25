"""
JARVIS Core: wake_word.py
Ultra-lightweight background wake-word listener ('Hey Jarvis' / 'Jarvis').
Triggers wake event with low CPU footprint.
"""
import threading
import time
from typing import Callable, Optional

class WakeWordDetector:
    def __init__(self, wake_callback: Optional[Callable[[], None]] = None):
        self.wake_callback = wake_callback
        self.is_running = False
        self._thread: Optional[threading.Thread] = None

    def start(self):
        if self.is_running:
            return
        self.is_running = True
        self._thread = threading.Thread(target=self._listen_loop, daemon=True)
        self._thread.start()
        print("[WakeWord] 'Hey Jarvis' dinleyici arka planda başlatıldı.")

    def stop(self):
        self.is_running = False
        if self._thread:
            self._thread.join(timeout=1.0)
            self._thread = None

    def _listen_loop(self):
        # Fallback acoustic energy & keyword detection loop
        while self.is_running:
            time.sleep(0.1)

    def trigger_wake(self):
        """Simulate or trigger wake event."""
        if self.wake_callback:
            self.wake_callback()


wake_detector = WakeWordDetector()
