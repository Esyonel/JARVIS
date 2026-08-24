import traceback
from typing import Any

try:
    from PIL import ImageGrab
except Exception:
    # Pillow might not be installed; fallback to a dummy implementation
    ImageGrab = None

try:
    import pytesseract
except Exception:
    pytesseract = None

# Plugin metadata following the strict contract
PLUGIN = {
    "name": "app_verification_ocr",
    "description": "Uses OCR (pytesseract) to verify that a specific application window is correctly displayed on the screen.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "app_name": {
                "type": "string",
                "description": "The expected textual identifier of the application (e.g., title bar text) that should be visible on the screen."
            }
        },
        "required": ["app_name"]
    }
}


def run(parameters: dict, player: Any = None, session_memory: Any = None) -> str:
    """Check if the expected application name appears on the screen using OCR.

    The function captures a screenshot of the primary monitor, runs OCR via
    ``pytesseract`` and looks for the provided ``app_name`` substring.
    It never raises; any error results in a user‑friendly message.
    """
    try:
        if pytesseract is None:
            return "OCR functionality is not available because pytesseract is not installed."
        if ImageGrab is None:
            return "Screen capture is not available because Pillow is not installed."

        app_name = parameters.get("app_name", "").strip()
        if not app_name:
            return "I need the name of the application to verify, but none was provided."

        # Capture the screen (full primary monitor)
        screenshot = ImageGrab.grab()
        # Perform OCR
        text = pytesseract.image_to_string(screenshot)
        # Simple case‑insensitive containment check
        if app_name.lower() in text.lower():
            return f"The application '{app_name}' appears to be displayed correctly."
        else:
            return f"I could not find '{app_name}' on the screen. The application may not have opened correctly."
    except Exception as e:
        # Log the traceback for debugging purposes if a player/logger is available
        if player and hasattr(player, "log"):
            player.log(traceback.format_exc())
        return f"An error occurred while verifying the application: {str(e)}"
