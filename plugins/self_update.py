"""Plugin to self-update JARVIS by pulling the latest code from git and
reinstalling any new dependencies.

JARVIS is a plain script-based app (run via `python main.py`), not an
installable pip package — there's no setup.py `setup()` call, no pyproject.toml.
An earlier version of this plugin ran `pip install -U .`, which pip can't do
anything with for a directory that isn't a real package; it always failed.
The actual update mechanism for a project like this is `git pull` +
reinstalling requirements.txt, same as a human maintainer would do.
"""

import subprocess
import sys
from pathlib import Path
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
                "description": "Git remote URL to pull updates from instead of origin (e.g. a fork). If omitted, pulls from origin."
            },
            "force": {
                "type": "boolean",
                "description": "Reserved for future use — currently has no effect. Uncommitted local changes always block the update rather than being discarded."
            }
        },
        "required": []
    }
}

BASE_DIR = Path(__file__).resolve().parent.parent


def run(parameters: Dict[str, Any], player=None, session_memory=None) -> str:
    """Pulls the latest commits via git, then reinstalls requirements.txt.

    Args:
        parameters: Dictionary matching the PLUGIN["parameters"] schema.
        player: Optional audio player (unused).
        session_memory: Optional session memory (unused).

    Returns:
        A short plain-text message suitable for voice output.
    """
    repo_url = parameters.get("repo_url")

    try:
        status = subprocess.run(
            ["git", "status", "--porcelain"], cwd=BASE_DIR,
            capture_output=True, text=True, check=False,
        )
        if status.returncode != 0:
            return f"Update failed: could not read git status ({status.stderr.strip()[:200]})."
        if status.stdout.strip():
            return ("Update skipped: there are uncommitted local changes in the JARVIS "
                    "folder. Commit or stash them first, then ask me to update again.")

        pull_cmd = ["git", "pull"]
        if repo_url:
            branch = subprocess.run(
                ["git", "branch", "--show-current"], cwd=BASE_DIR,
                capture_output=True, text=True, check=False,
            ).stdout.strip() or "main"
            pull_cmd = ["git", "pull", repo_url, branch]

        pull = subprocess.run(pull_cmd, cwd=BASE_DIR, capture_output=True, text=True, check=False)
        if pull.returncode != 0:
            error_msg = (pull.stderr or pull.stdout).strip() or "unknown error"
            return f"Update failed: {error_msg[:300]}"

        output = (pull.stdout or "").strip()
        if "Already up to date" in output or "already up-to-date" in output.lower():
            return "JARVIS is already up to date."

        pip_result = subprocess.run(
            [sys.executable, "-m", "pip", "install", "-r", "requirements.txt", "--quiet"],
            cwd=BASE_DIR, capture_output=True, text=True, check=False,
        )
        if pip_result.returncode != 0:
            return (f"Code updated but installing new dependencies failed: "
                    f"{pip_result.stderr.strip()[:300]}. Restart JARVIS, then run "
                    "'pip install -r requirements.txt' manually.")

        return "Update completed successfully. Please restart JARVIS to apply the changes."
    except Exception as exc:
        return f"An error occurred while updating: {exc}"
