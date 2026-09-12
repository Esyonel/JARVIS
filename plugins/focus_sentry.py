"""
plugins/focus_sentry.py — real idle-time tracking + break reminders.

check_idle reads actual OS idle time (Windows: GetLastInputInfo via ctypes —
no new dependency; other platforms return an honest "not supported" instead
of a fake number). trigger_break fires a real native toast via win10toast,
already in requirements.txt but never wired up until now.
"""
import sys
from typing import Optional

PLUGIN = {
    "name": "focus_sentry",
    "description": (
        "Kullanıcının bilgisayardaki gerçek boşta kalma süresini ölçer ve "
        "Pomodoro molası bildirimi gönderir (Windows'ta gerçek sistem "
        "bildirimi). 'ne kadar süredir boştayım', 'pomodoro molasını hatırlat' "
        "gibi komutlarda kullanılır."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "description": "'check_idle' (boşta kalma süresini ölç), 'trigger_break' (mola bildirimi gönder)."
            }
        },
        "required": ["action"]
    }
}


def _idle_seconds_windows() -> Optional[float]:
    try:
        import ctypes

        class LASTINPUTINFO(ctypes.Structure):
            _fields_ = [("cbSize", ctypes.c_uint), ("dwTime", ctypes.c_uint)]

        info = LASTINPUTINFO()
        info.cbSize = ctypes.sizeof(LASTINPUTINFO)
        if not ctypes.windll.user32.GetLastInputInfo(ctypes.byref(info)):
            return None
        millis_idle = ctypes.windll.kernel32.GetTickCount() - info.dwTime
        return millis_idle / 1000.0
    except Exception:
        return None


def run(parameters: dict, player=None, session_memory=None) -> str:
    action = str(parameters.get("action", "check_idle")).strip().lower()

    if action == "check_idle":
        if sys.platform != "win32":
            return "Boşta kalma süresi ölçümü şu an yalnızca Windows'ta destekleniyor."
        idle = _idle_seconds_windows()
        if idle is None:
            return "Boşta kalma süresi okunamadı."
        if idle < 5:
            return "Aktif olarak kullanılıyorsunuz."
        return f"{idle:.0f} saniyedir bilgisayarda hareket yok."

    elif action == "trigger_break":
        message = "Biraz esneme hareketleri yapın, gözlerinizi dinlendirin."
        sent = False
        if sys.platform == "win32":
            try:
                from win10toast import ToastNotifier
                ToastNotifier().show_toast("Pomodoro Molası", message, duration=8, threaded=True)
                sent = True
            except Exception:
                sent = False
        if player:
            try:
                player.write_log(f"SYS: Pomodoro molası — {message}")
            except Exception:
                pass
        return ("Pomodoro molası bildirimi gönderildi." if sent
                else f"Pomodoro molası: {message}")

    return f"Bilinmeyen eylem: {action}"
