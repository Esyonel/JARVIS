"""Plugin to self‑update JARVIS for advanced features and performance improvements.

The plugin can pull the latest code from a git repository (if provided) or update the
current installation via ``pip install -U .``. It returns a short spoken response
indicating success or failure.
"""

import sys
import subprocess
from typing import Any, Dict

# Plugin metadata consumed by the core plugin loader
PLUGIN = {
    "name": "self_update",
    "description": "Checks for updates of JARVIS and installs them to improve features and performance.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "repo_url": {
                "type": "string",
                "description": "Git repository URL to pull updates from. If omitted, updates the current installation."
            },
            "force": {
                "type": "boolean",
                "description": "Force re‑installation even if no new version is detected."
            }
        },
        "required": []
    }
}


def run(parameters: Dict[str, Any], player=None, session_memory=None) -> str:
    """Execute the self‑update routine.

    Args:
        parameters: Dictionary matching the PLUGIN["parameters"] schema.
        player: Optional audio player (unused).
        session_memory: Optional session memory (unused).

    Returns:
        A short plain‑text message suitable for voice output.
    """
    repo_url = parameters.get("repo_url")
    # ``force`` currently does not change behaviour because ``pip install -U``
    # already forces an upgrade if a newer version is available. It is kept for
    # future extensibility.
    _ = parameters.get("force", False)

    try:
        if repo_url:
            # Update directly from the supplied git repository.
            cmd = [sys.executable, "-m", "pip", "install", "-U", f"git+{repo_url}"]
        else:
            # Update the package from the current working directory.
            cmd = [sys.executable, "-m", "pip", "install", "-U", "."]

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=False,
        )

        if result.returncode == 0:
            return "Update completed successfully. Please restart JARVIS to apply the changes."
        else:
            error_msg = result.stderr.strip() or "unknown error"
            return f"Update failed: {error_msg}"
    except Exception as exc:
        return f"An error occurred while updating: {exc}"