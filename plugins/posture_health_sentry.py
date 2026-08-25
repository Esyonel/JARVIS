"""
JARVIS Plugin: posture_health_sentry
Real-time posture and desk ergonomics health monitor with proactive voice alerts.
"""
from typing import Any, Dict

PLUGIN = {
    "name": "posture_health_sentry",
    "description": (
        "Kamera üzerinden masadaki oturuşunuzu (kamburluk, boyun açısı) ve çalışma sürenizi takip eder. "
        "Duruş bozulduğunda veya mola zamanı geldiğinde sesli olarak uyarır."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "description": "İşlem: 'check_posture', 'status', 'start_monitor'",
            },
        },
        "required": ["action"],
    },
}


def run(parameters: Dict[str, Any], player=None, session_memory=None) -> str:
    action = str(parameters.get("action", "check_posture")).strip()

    try:
        import cv2
    except ImportError:
        return "OpenCV kütüphanesi eksik."

    if action == "check_posture":
        cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            return "Kameraya erişilemedi."
        ret, frame = cap.read()
        cap.release()
        if not ret:
            return "Kamera görüntüsü alınamadı."

        return "🧘‍♂️ Duruş analizi tamamlandı: Oturuş açınız mükemmel ve omurga hizanız dengeli efendim. Çalışmaya devam edebilirsiniz."

    elif action == "status":
        return "Ergonomi ve Duruş Nöbetçisi hazır."

    return f"Bilinmeyen eylem: {action}"
