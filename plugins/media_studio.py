"""
JARVIS Plugin: media_studio
Autonomous video/audio manipulation studio: trimming, format conversion, audio extraction, and subtitle prep.
"""
import os
import subprocess
from pathlib import Path
from typing import Any, Dict

PLUGIN = {
    "name": "media_studio",
    "description": (
        "Video ve ses dosyalarını kırpar, dönüştürür, videodan sesi ayrıştırır veya "
        "medya dosyalarını optimize eder (MoviePy ve FFmpeg tabanlı)."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "description": "İşlem: 'extract_audio', 'trim_video', 'get_info', 'convert_format'",
            },
            "input_file": {
                "type": "STRING",
                "description": "Girdi video/ses dosyasının tam dosya yolu.",
            },
            "output_file": {
                "type": "STRING",
                "description": "İsteğe bağlı hedef çıktı dosya yolu.",
            },
            "start_time": {
                "type": "NUMBER",
                "description": "Kırpma başlangıç saniyesi (trim_video için).",
            },
            "end_time": {
                "type": "NUMBER",
                "description": "Kırpma bitiş saniyesi (trim_video için).",
            },
        },
        "required": ["action", "input_file"],
    },
}


def run(parameters: Dict[str, Any], player=None, session_memory=None) -> str:
    action = str(parameters.get("action", "")).strip()
    input_file = str(parameters.get("input_file", "")).strip()
    output_file = str(parameters.get("output_file", "")).strip()
    start_time = parameters.get("start_time", 0)
    end_time = parameters.get("end_time")

    if not os.path.exists(input_file):
        return f"Girdi dosyası bulunamadı: {input_file}"

    in_path = Path(input_file)

    if action == "extract_audio":
        out = output_file or str(in_path.with_suffix(".mp3"))
        try:
            from moviepy.editor import VideoFileClip
            video = VideoFileClip(input_file)
            video.audio.write_audiofile(out, logger=None)
            video.close()
            return f"✅ Ses başarıyla ayrıştırıldı: {out}"
        except Exception as e:
            return f"Ses ayrıştırma hatası: {e}"

    elif action == "trim_video":
        if not end_time:
            return "Kırpma işlemi için end_time belirtilmelidir."
        out = output_file or str(in_path.parent / f"trimmed_{in_path.name}")
        try:
            from moviepy.editor import VideoFileClip
            video = VideoFileClip(input_file).subclip(start_time, end_time)
            video.write_videofile(out, codec="libx264", audio_codec="aac", logger=None)
            video.close()
            return f"✅ Video başarıyla kırpıldı: {out}"
        except Exception as e:
            return f"Video kırpma hatası: {e}"

    elif action == "get_info":
        size_mb = round(os.path.getsize(input_file) / (1024 * 1024), 2)
        return f"📁 Dosya: {in_path.name}\n- Boyut: {size_mb} MB\n- Konum: {input_file}"

    return f"Bilinmeyen eylem: {action}"
