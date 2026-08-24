import platform
import traceback

# Optional imports for window title detection on Windows
try:
    import win32gui  # type: ignore
except Exception:
    win32gui = None

# Optional import for macOS title detection
try:
    import subprocess  # used for both macOS and Linux fallback commands
except Exception:
    subprocess = None

PLUGIN = {
    "name": "app_website_verifier",
    "description": (
        "Kullanıcı tarafından belirtilen uygulama penceresinin başlığını veya web sitesinin "
        "URL/başlık bilgisini kontrol eder ve açılan içeriğin doğru olup olmadığını doğrular. "
        "Bu eklenti, JARVIS'in bir uygulama ya da web sayfası açtıktan sonra "
        "kullanıcıya onay vermesini sağlar."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "mode": {
                "type": "STRING",
                "description": "'app' veya 'web' değerlerinden biri. 'app' uygulama penceresini, 'web' web sitesini doğrular."
            },
            "expected": {
                "type": "STRING",
                "description": (
                    "Uygulama penceresinde (title) veya web sitesinin URL/başlık kısmında "
                    "beklenen metin. Büyük/küçük harf duyarsız olarak içerik kontrolü yapılır."
                )
            }
        },
        "required": ["mode", "expected"]
    }
}


def _get_active_window_title() -> str:
    """Return the title of the currently active/focused window.
    Supports Windows, macOS and Linux (X11) on a best‑effort basis.
    If the platform cannot be determined or an error occurs, returns an empty string.
    """
    system = platform.system()
    try:
        if system == "Windows" and win32gui:
            hwnd = win32gui.GetForegroundWindow()
            return win32gui.GetWindowText(hwnd)
        elif system == "Darwin":  # macOS
            # Use AppleScript to get the frontmost application name and window title
            script = (
                "tell application \"System Events\" to get name of first process whose frontmost is true"
            )
            proc = subprocess.run(
                ["osascript", "-e", script], capture_output=True, text=True
            )
            app_name = proc.stdout.strip()
            # Try to get the window title of the frontmost app (works for many browsers)
            script = (
                f"tell application \"{app_name}\" to get name of front window"
            )
            proc = subprocess.run(
                ["osascript", "-e", script], capture_output=True, text=True
            )
            return proc.stdout.strip()
        elif system == "Linux":
            # Use xprop to fetch the active window title (requires X11)
            # First get the active window id
            id_proc = subprocess.run(
                ["xprop", "-root", "_NET_ACTIVE_WINDOW"], capture_output=True, text=True
            )
            if id_proc.returncode != 0:
                return ""
            # Extract window id (hex)
            parts = id_proc.stdout.strip().split()
            if len(parts) < 5:
                return ""
            win_id = parts[-1]
            # Now get the WM_NAME property
            name_proc = subprocess.run(
                ["xprop", "-id", win_id, "WM_NAME"], capture_output=True, text=True
            )
            if name_proc.returncode != 0:
                return ""
            # Output format: WM_NAME(STRING) = "Title"
            title_part = name_proc.stdout.split('=')[-1].strip()
            if title_part.startswith('"') and title_part.endswith('"'):
                title_part = title_part[1:-1]
            return title_part
    except Exception:
        # Silently ignore any platform‑specific failures
        return ""
    return ""


def run(parameters: dict, player=None, session_memory=None) -> str:
    """Validate that the requested application or website is currently active.

    Parameters
    ----------
    parameters: dict
        Expected keys:
        - "mode": "app" or "web"
        - "expected": substring that should appear in the window title (for apps) or in the title/URL of the browser (for web).
    player, session_memory: unused but kept for plugin compatibility.

    Returns
    -------
    str
        A short Turkish sentence that JARVIS can speak, indicating success or failure.
    """
    try:
        mode = str(parameters.get("mode", "")).lower()
        expected = str(parameters.get("expected", "")).strip()
        if mode not in {"app", "web"}:
            return "Geçersiz doğrulama modu. 'app' veya 'web' değerlerinden biri kullanılmalı."
        if not expected:
            return "Doğrulama için beklenen metin sağlanmadı."

        title = _get_active_window_title()
        if not title:
            return "Aktif pencere başlığı alınamadı, doğrulama yapılamıyor."

        if expected.lower() in title.lower():
            return f"Doğrulama başarılı: {mode} beklenen içerikle eşleşti."
        else:
            # Provide a helpful hint showing what was found
            return (
                f"Doğrulama başarısız: aktif {mode} pencere başlığı '{title}' "
                f"beklenen '{expected}' ifadesini içermiyor."
            )
    except Exception as e:
        # Log the traceback for debugging (if a logger exists, otherwise ignore)
        try:
            import logging
            logging.error("App/Website verification error: %s", traceback.format_exc())
        except Exception:
            pass
        return f"Doğrulama sırasında bir hata oluştu: {e}"  
