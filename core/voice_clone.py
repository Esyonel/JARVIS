"""
JARVIS Core: voice_clone.py
Custom voice cloning management: loads reference audio (e.g. Paul Bettany JARVIS or custom sample)
and registers it with TTS engines.
"""
from pathlib import Path
from typing import Any, Dict, Optional

_VOICES_DIR = Path(__file__).resolve().parent.parent / "config" / "cloned_voices"


class VoiceCloningStudio:
    def __init__(self):
        self.voices_dir = _VOICES_DIR
        self.voices_dir.mkdir(parents=True, exist_ok=True)

    def list_cloned_voices(self) -> list[str]:
        return [f.stem for f in self.voices_dir.glob("*.wav")]

    def set_reference_audio(self, voice_name: str, audio_file_path: str) -> Dict[str, Any]:
        import shutil
        target = self.voices_dir / f"{voice_name}.wav"
        try:
            shutil.copy(audio_file_path, target)
            return {"success": True, "message": f"{voice_name} ses referansı başarıyla kaydedildi."}
        except Exception as e:
            return {"success": False, "error": str(e)}


voice_studio = VoiceCloningStudio()
