"""
JARVIS Dashboard Component: notification_bridge.py
Handles incoming mobile notifications, phone calls, and SMS from android-remote
and delivers HUD overlay popups and audio announcements.
"""
from typing import Any, Dict, List
import time

_RECENT_NOTIFICATIONS: List[Dict[str, Any]] = []


def push_mobile_notification(title: str, message: str, app: str = "System") -> Dict[str, Any]:
    entry = {
        "title": title,
        "message": message,
        "app": app,
        "timestamp": time.time(),
    }
    _RECENT_NOTIFICATIONS.append(entry)
    if len(_RECENT_NOTIFICATIONS) > 50:
        _RECENT_NOTIFICATIONS.pop(0)

    # Trigger Windows toast if available
    try:
        from win10toast import ToastNotifier
        toaster = ToastNotifier()
        toaster.show_toast(f"📱 {app}: {title}", message, duration=4, threaded=True)
    except Exception:
        pass

    return {"success": True, "entry": entry}


def get_recent_notifications(limit: int = 10) -> List[Dict[str, Any]]:
    return _RECENT_NOTIFICATIONS[-limit:]
