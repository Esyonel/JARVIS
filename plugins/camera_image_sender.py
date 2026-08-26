'''Plugin: camera_image_sender

Capture an image using the existing ``camera_capture`` plugin and forward the
resulting picture to the user via Telegram (or any configured messaging bridge).
The plugin follows the standard JARVIS plugin contract: a ``PLUGIN`` dict that
describes the plugin and a ``run`` function that returns a short spoken response.
All errors are caught and turned into user‑friendly messages so the assistant
never raises an exception to the caller.
''' 

from __future__ import annotations

import os
import traceback
from typing import Any, Dict

# Import the existing camera capture plugin – it already knows how to talk to the
# webcam and returns the absolute path of the saved image.
try:
    from plugins.camera_capture import run as capture_image
except Exception:  # pragma: no cover – defensive import
    capture_image = None  # type: ignore

# Import the Telegram bridge – this is the most common channel used by JARVIS
# to deliver media to the user.  If the bridge is unavailable we simply skip the
# sending step and inform the user.
try:
    from core.telegram_bridge import TelegramBridge
except Exception:  # pragma: no cover – defensive import
    TelegramBridge = None  # type: ignore

# ---------------------------------------------------------------------------
# Plugin metadata – JARVIS reads this to expose the capability in its UI.
# ---------------------------------------------------------------------------
PLUGIN = {
    "name": "camera_image_sender",
    "description": "Capture a picture with the webcam and send it to the user via Telegram.",
    "parameters": {
        "type": "OBJECT",
        "properties": {},
        "required": [],
    },
}


def _send_via_telegram(image_path: str) -> str:
    """Attempt to send *image_path* using the Telegram bridge.

    Returns a human‑readable status message.  All exceptions are caught and
    transformed into a string so the outer ``run`` never propagates errors.
    """
    if not TelegramBridge:
        return "Telegram bridge is not available; image was saved locally."
    try:
        bridge = TelegramBridge()
        # ``send_image`` is the conventional method name used throughout the
        # code‑base.  If the implementation differs, the ``except`` block will
        # capture the AttributeError and fallback to a generic message.
        if hasattr(bridge, "send_image"):
            bridge.send_image(image_path)
            return "Image sent to you via Telegram."
        elif hasattr(bridge, "send_media"):
            bridge.send_media(image_path)
            return "Image sent to you via Telegram."
        else:
            return "Telegram bridge does not expose an image‑send method; image saved locally."
    except Exception as exc:  # pragma: no cover – defensive
        # Log the traceback for debugging (JARVIS logs to its internal logger).
        try:
            import logging
            logging.getLogger(__name__).exception("Failed to send image via Telegram")
        finally:
            return f"Failed to send image via Telegram: {exc}"


def run(parameters: Dict[str, Any], player=None, session_memory=None) -> str:  # noqa: D401
    """Capture a webcam image and forward it to the user.

    The function follows the JARVIS plugin contract: it must return a **short**
    plain‑text string that will be spoken aloud.  All internal errors are caught
    and reported as user‑friendly messages.
    """
    # ---------------------------------------------------------------------
    # 1️⃣ Capture the image using the existing plugin.
    # ---------------------------------------------------------------------
    if not capture_image:
        return "Camera capture capability is not available."
    try:
        image_path = capture_image({})
        if not isinstance(image_path, str) or not os.path.isfile(image_path):
            return "Failed to capture an image with the camera."
    except Exception as exc:  # pragma: no cover – defensive
        return f"Error while capturing image: {exc}"

    # ---------------------------------------------------------------------
    # 2️⃣ Send the image via Telegram (if possible).
    # ---------------------------------------------------------------------
    send_status = _send_via_telegram(image_path)

    # ---------------------------------------------------------------------
    # 3️⃣ Return a concise spoken response.
    # ---------------------------------------------------------------------
    if "sent" in send_status.lower():
        return "I took a picture and sent it to you."
    else:
        # Include the local path so the user knows where to find the file.
        return f"I took a picture but could not send it. You can find it at {image_path}."
