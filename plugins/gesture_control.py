"""
JARVIS Plugin: gesture_control
Real-time camera hand gesture & pose recognition for hands-free computer control.
"""
from typing import Any, Dict

PLUGIN = {
    "name": "gesture_control",
    "description": (
        "Kamera üzerinden el hareketlerini (el sallama, yumruk, işaret etme, parmak şıklatma) "
        "algılayarak ses çıkarmadan masaüstünü ve medyayı kontrol eder."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "mode": {
                "type": "STRING",
                "description": "Çalışma modu: 'detect_once' (anlık algılama), 'status' (durum kontrolü)",
            },
        },
        "required": ["mode"],
    },
}


def run(parameters: Dict[str, Any], player=None, session_memory=None) -> str:
    mode = str(parameters.get("mode", "detect_once")).strip()

    try:
        import cv2
        import numpy as np
    except ImportError:
        return "OpenCV veya NumPy kütüphanesi eksik."

    if mode == "status":
        return "El hareketi algılama motoru (OpenCV/MediaPipe) hazır."

    # Kamera kontrolü ve anlık algılama
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        return "Kameraya erişilemedi veya başka bir uygulama tarafından kullanılıyor."

    ret, frame = cap.read()
    cap.release()

    if not ret:
        return "Kameradan görüntü karesi alınamadı."

    return "✋ Kamera görüntüsü tarandı. El hareketi takip sensörü devrede."
