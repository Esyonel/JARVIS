import traceback

# Plugin definition following the JARVIS plugin contract
PLUGIN = {
    "name": "move_cursor",
    "description": "Move the mouse cursor to a specific screen coordinate.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "x": {
                "type": "integer",
                "description": "Horizontal screen coordinate in pixels."
            },
            "y": {
                "type": "integer",
                "description": "Vertical screen coordinate in pixels."
            }
        },
        "required": ["x", "y"]
    }
}


def run(parameters: dict, player=None, session_memory=None) -> str:
    """Move the mouse cursor to the given (x, y) screen coordinates.

    Parameters
    ----------
    parameters: dict
        Must contain integer keys "x" and "y".
    player, session_memory: optional
        Ignored for this plugin but kept for signature compatibility.

    Returns
    -------
    str
        A short spoken confirmation or an error message.
    """
    try:
        # Extract and validate coordinates
        x = int(parameters.get("x"))
        y = int(parameters.get("y"))

        # Lazy import to avoid unnecessary dependency loading if not used
        import pyautogui

        # Move the cursor; duration=0 makes it instant
        pyautogui.moveTo(x, y, duration=0)
        return f"Mouse moved to coordinates ({x}, {y})."
    except Exception as e:
        # Log the traceback for debugging purposes (if a logger is available)
        traceback_str = traceback.format_exc()
        # In production we might send this to a logger; here we just include the error message.
        return f"Failed to move mouse: {e}."
