import pyautogui
import pytesseract
from typing import Any

# Plugin metadata
PLUGIN = {
    "name": "app_verification_screenshot",
    "description": "Açılan uygulamanın ekran görüntüsü üzerinden OCR ile doğrulanması.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "expected_app": {
                "type": "string",
                "description": "Doğrulanması istenen uygulamanın adı (pencere başlığı ya da ekrandaki metin)."
            }
        },
        "required": ["expected_app"]
    }
}


def run(parameters: dict, player: Any = None, session_memory: Any = None) -> str:
    """Take a screenshot, run OCR and check if the expected application name appears.

    Args:
        parameters: Must contain "expected_app" key.
        player: Unused, kept for compatibility with other plugins.
        session_memory: Unused, kept for compatibility.

    Returns:
        A short Turkish string that can be spoken to the user.
    """
    try:
        expected_app = parameters.get("expected_app", "").strip()
        if not expected_app:
            return "Lütfen doğrulamak istediğiniz uygulama adını belirtin."

        # Capture the whole screen
        screenshot = pyautogui.screenshot()
        # Perform OCR using pytesseract
        ocr_text = pytesseract.image_to_string(screenshot)
        if expected_app.lower() in ocr_text.lower():
            return f"{expected_app} uygulaması doğru şekilde açılmış ve ekranda tespit edildi."
        else:
            return f"{expected_app} uygulaması ekran görüntüsünde bulunamadı."
    except Exception as e:
        return f"Uygulama doğrulaması sırasında bir hata oluştu: {str(e)}"
