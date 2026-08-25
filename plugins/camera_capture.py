"""
camera_capture plugin — takes a photo or records a short video from the webcam
and shows the result on JARVIS's screen (the same HUD area used for the live
camera feed / content panel).

Reuses the camera-index detection and backend selection already built for the
vision feature in actions/screen_processor.py, so it opens whichever camera
JARVIS already knows how to find.
"""
from __future__ import annotations

import time
from datetime import datetime
from pathlib import Path

try:
    import cv2
    _CV2 = True
except ImportError:
    _CV2 = False

from actions.screen_processor import _capture_camera, _cv2_backend, _get_camera_index

PLUGIN = {
    "name": "camera_capture",
    "description": (
        "Takes a photo or records a short video clip from the webcam and displays it "
        "on JARVIS's screen. Use for requests like 'fotoğraf çek', 'resim çek', "
        "'bir fotoğrafımı çek', 'video çek', 'video kaydet', 'beni kaydet'. This is for "
        "capturing and showing a photo/video, not for analyzing what the camera currently "
        "sees — use the live vision tool for that."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "mode": {
                "type": "STRING",
                "description": "'photo' (default) to take a single picture, or 'video' to record a short clip.",
            },
            "duration": {
                "type": "INTEGER",
                "description": "Video recording length in seconds (mode='video' only). Default 6, clamped to 2-20.",
            },
        },
        "required": [],
    },
}


def _captures_dir(kind: str) -> Path:
    """Cross-platform capture folder, mirroring dashboard/server.py's uploads-dir pattern."""
    base = Path(__file__).resolve().parent.parent
    for candidate in [
        Path.home() / kind / "JARVIS Captures",
        base / "captures",
    ]:
        try:
            candidate.mkdir(parents=True, exist_ok=True)
            return candidate
        except Exception:
            continue
    return base / "captures"


def _take_photo(player) -> str:
    img_bytes, _mime = _capture_camera()

    out_path = _captures_dir("Pictures") / f"jarvis_{datetime.now():%Y%m%d_%H%M%S}.jpg"
    out_path.write_bytes(img_bytes)

    if player:
        try:
            player.show_camera_frame(img_bytes)
        except Exception:
            pass

    return f"Fotoğraf çekildi ve ekranda gösteriliyor. Kaydedildi: {out_path}"


def _record_video(player, duration: float) -> str:
    if not _CV2:
        return "OpenCV yüklü değil, video kaydedilemedi."

    index   = _get_camera_index()
    backend = _cv2_backend()
    cap     = cv2.VideoCapture(index, backend)
    if not cap.isOpened():
        return f"Kamera (index {index}) açılamadı."

    try:
        for _ in range(10):
            cap.read()

        fps = cap.get(cv2.CAP_PROP_FPS)
        if not fps or fps <= 1 or fps > 60:
            fps = 20.0
        width  = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)) or 640
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)) or 480

        out_path = _captures_dir("Videos") / f"jarvis_{datetime.now():%Y%m%d_%H%M%S}.mp4"
        writer = cv2.VideoWriter(
            str(out_path), cv2.VideoWriter_fourcc(*"mp4v"), fps, (width, height)
        )

        end_time = time.time() + duration
        frames_written = 0
        while time.time() < end_time:
            ret, frame = cap.read()
            if not ret or frame is None:
                break
            writer.write(frame)
            frames_written += 1
        writer.release()
    finally:
        cap.release()

    if frames_written == 0:
        return "Video kaydedilemedi, kameradan görüntü alınamadı."

    if player:
        try:
            player.show_video(str(out_path))
        except Exception:
            pass

    return f"{duration:.0f} saniyelik video kaydedildi ve ekranda oynatılıyor. Kaydedildi: {out_path}"


def run(parameters: dict, player=None, session_memory=None) -> str:
    mode = (parameters.get("mode") or "photo").strip().lower()

    try:
        if mode == "video":
            duration = parameters.get("duration") or 6
            duration = max(2, min(20, int(duration)))
            return _record_video(player, duration)
        return _take_photo(player)
    except Exception as e:
        return f"Kamera işlemi başarısız oldu: {e}"
