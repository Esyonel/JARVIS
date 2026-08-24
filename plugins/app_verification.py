import os
import tempfile
import traceback

try:
    # PyQt6 is already used in the project for the GUI
    from PyQt6.QtGui import QGuiApplication
except Exception:
    QGuiApplication = None

# Optional OCR support – only used if pytesseract is available
try:
    import pytesseract
    from PIL import Image
except Exception:
    pytesseract = None
    Image = None

PLUGIN = {
    "name": "app_verification",
    "description": "Açılan uygulamanın doğru olup olmadığını ekran görüntüsüyle kontrol eder ve kullanıcıya bilgi verir.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "expected_title": {
                "type": "string",
                "description": "Beklenen pencere başlığı (örnek: 'Google Chrome')"
            }
        },
        "required": ["expected_title"]
    }
}


def _capture_active_window() -> str:
    """Capture the currently active window and return the file path of the saved image.
    Returns an empty string on failure.
    """
    if QGuiApplication is None:
        return ""
    try:
        app = QGuiApplication.instance()
        if app is None:
            app = QGuiApplication([])
        screen = app.primaryScreen()
        if screen is None:
            return ""
        # 0 means the currently active window (platform dependent)
        pixmap = screen.grabWindow(0)
        if pixmap.isNull():
            return ""
        fd, path = tempfile.mkstemp(suffix=".png")
        os.close(fd)  # we will let Qt write the file
        pixmap.save(path, "png")
        return path
    except Exception:
        return ""


def _extract_window_title(image_path: str) -> str:
    """Attempt to read the window title from a screenshot using OCR.
    Returns an empty string if OCR is unavailable or fails.
    """
    if pytesseract is None or Image is None:
        return ""
    try:
        img = Image.open(image_path)
        text = pytesseract.image_to_string(img, lang="eng")
        # Take the first line as the most likely title
        title = text.splitlines()[0].strip()
        return title
    except Exception:
        return ""


def run(parameters: dict, player=None, session_memory=None) -> str:
    """Take a screenshot of the active window, optionally run OCR to compare with the expected title,
    and return a short spoken response.
    """
    try:
        expected = parameters.get("expected_title", "").strip()
        if not expected:
            return "Beklenen pencere başlığı belirtilmedi."

        screenshot_path = _capture_active_window()
        if not screenshot_path:
            return "Ekran görüntüsü alınamadı, lütfen uygulamayı tekrar açın."

        # Try to read the title via OCR if possible
        actual_title = _extract_window_title(screenshot_path)
        # Clean up the temporary screenshot file
        try:
            os.remove(screenshot_path)
        except Exception:
            pass

        if actual_title:
            if expected.lower() in actual_title.lower():
                return f"Uygulama doğru şekilde açıldı: {actual_title}."
            else:
                return f"Uygulama beklenen başlığa sahip değil. Bulunan: {actual_title}, beklenen: {expected}."
        else:
            # Fallback when OCR is not available – just inform that screenshot was taken
            return f"Ekran görüntüsü alındı, ancak pencere başlığı doğrulanamadı. Lütfen {expected} uygulamasının açık olduğunu kontrol edin."
    except Exception as e:
        # Ensure we never raise an exception to the assistant core
        err = traceback.format_exc()
        return f"Uygulama doğrulama sırasında bir hata oluştu: {str(e)}"
