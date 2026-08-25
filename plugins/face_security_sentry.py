"""
JARVIS Plugin: face_security_sentry
Biometric Face ID authentication, greeting, and intruder security sentry.
"""
from typing import Any, Dict
from core.face_id import face_engine

PLUGIN = {
    "name": "face_security_sentry",
    "description": (
        "Kamera üzerinden kullanıcının yüzünü tanır, biyometrik kimlik doğrulaması yapar, "
        "kullanıcıyı karşılar veya yabancı algılandığında güvenlik uyarısı verir."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "description": "İşlem: 'verify', 'enroll', 'status'",
            },
        },
        "required": ["action"],
    },
}


def run(parameters: Dict[str, Any], player=None, session_memory=None) -> str:
    action = str(parameters.get("action", "verify")).strip()

    if action == "enroll":
        res = face_engine.enroll_face()
        if res.get("success"):
            return "👤 Yüz biyometriğiniz başarıyla kaydedildi. Artık yüz tanıma ile oturum doğrulayabilirsiniz."
        return f"Yüz kaydı başarısız: {res.get('error')}"

    elif action == "verify":
        res = face_engine.verify_user()
        if res.get("verified"):
            return "✅ Hoş geldiniz efendim. Biyometrik yüz kimliğiniz doğrulandı."
        return f"❌ Kimlik doğrulanamadı: {res.get('error', 'Kullanıcı algılanamadı.')}"

    elif action == "status":
        enrolled = "Kayıtlı" if face_engine.is_enrolled() else "Kayıt Yok"
        return f"Yüz Tanıma Durumu: {enrolled}"

    return f"Bilinmeyen eylem: {action}"
