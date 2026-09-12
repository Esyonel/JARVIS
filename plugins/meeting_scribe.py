"""
plugins/meeting_scribe.py — meeting audio → real transcript.

Reuses core/stt.py's WhisperSTT (the same model class main.py uses for the
live mic) on an arbitrary audio FILE instead of live mic input. Deliberately
does NOT call a second LLM to extract action items — the transcript comes
back as the tool result, and Gemini (already in this conversation) is the
one that reads it and pulls out action items, exactly like every other
plugin in this codebase hands back data rather than a pre-written answer.
"""
import time
from pathlib import Path

_BASE = Path(__file__).resolve().parent.parent / "memory"
_MEETINGS_DIR = _BASE / "meetings"

PLUGIN = {
    "name": "meeting_scribe",
    "description": (
        "Bir toplantı ses kaydını (wav/mp3/m4a) gerçek Whisper modeliyle metne "
        "döker ve hafızaya kaydeder. Dökümü döner — action item/özet çıkarımını "
        "siz (JARVIS) döküm üzerinden konuşarak yaparsınız. 'şu ses kaydını "
        "yazıya dök' gibi komutlarda kullanılır."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "description": "'transcribe' (ses dosyasını yazıya dök), 'list' (kaydedilmiş dökümleri listele)."
            },
            "audio_path": {
                "type": "STRING",
                "description": "'transcribe' için ses dosyasının tam yolu."
            }
        },
        "required": ["action"]
    }
}

_whisper = None


def _get_whisper():
    global _whisper
    if _whisper is None:
        from core.stt import WhisperSTT
        _whisper = WhisperSTT(model_name="base")
    return _whisper


def run(parameters: dict, player=None, session_memory=None) -> str:
    action = str(parameters.get("action", "transcribe")).strip().lower()

    if action == "list":
        if not _MEETINGS_DIR.exists():
            return "Kaydedilmiş toplantı dökümü yok."
        files = sorted(_MEETINGS_DIR.glob("*.txt"), reverse=True)
        if not files:
            return "Kaydedilmiş toplantı dökümü yok."
        return "Kayıtlı dökümler: " + ", ".join(f.stem for f in files[:20])

    elif action == "transcribe":
        audio_path = str(parameters.get("audio_path", "")).strip()
        if not audio_path or not Path(audio_path).exists():
            return "Geçerli bir ses dosyası yolu belirtmelisiniz."

        try:
            import librosa
            audio, _ = librosa.load(audio_path, sr=16000, mono=True)
        except Exception as e:
            return f"Ses dosyası okunamadı: {e}"

        try:
            whisper = _get_whisper()
            transcript = whisper.transcribe(audio.astype("float32"))
        except Exception as e:
            return f"Transkripsiyon başarısız: {e}"

        if not transcript:
            return "Ses dosyasında anlaşılır konuşma bulunamadı."

        _MEETINGS_DIR.mkdir(parents=True, exist_ok=True)
        ts = time.strftime("%Y%m%d_%H%M%S")
        out_path = _MEETINGS_DIR / f"{ts}.txt"
        out_path.write_text(transcript, encoding="utf-8")

        if player:
            try:
                player.write_log(f"SYS: Toplantı dökümü kaydedildi — {out_path.name}")
            except Exception:
                pass
        return f"Döküm ({out_path.name}):\n{transcript}"

    return f"Bilinmeyen eylem: {action}"
