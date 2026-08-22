"""
JARVIS plugin — find and launch a project by name.

Searches a configured root folder (default D:\\nu, or wherever JARVIS itself
lives if that doesn't exist) for a subfolder matching the spoken project
name, then runs the most likely start script inside it (.bat/.command first,
then main.py/app.py/run.py). Launched detached (Popen, not waited on) since
these are typically long-running bots/servers.
"""

import re
import subprocess
import sys
from pathlib import Path

PLUGIN = {
    "name": "project_launcher",
    "description": (
        "Finds a project folder by name and launches its start script "
        "(.bat, .command, or main.py/app.py/run.py). Use for: "
        "'Borsa botunu başlat', 'launch the trading bot project', "
        "'kasa programını çalıştır'. Give the project name as it would "
        "appear in the folder name, not the full path."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "project_name": {
                "type": "STRING",
                "description": "Name (or fragment) of the project folder to launch, e.g. 'Borsa_botu'.",
            },
        },
        "required": ["project_name"],
    },
}

_ROOTS = [Path("D:/nu"), Path.home()]
_SCRIPT_PRIORITY = ["*.bat", "*.command", "main.py", "app.py", "run.py", "start.py"]
_IGNORE_DIRS = {".git", ".venv", "venv", "__pycache__", "node_modules", ".idea", ".vscode"}


def run(parameters: dict, player=None, session_memory=None) -> str:
    name = (parameters.get("project_name") or "").strip()
    if not name:
        msg = "Sir, I need a project name to launch."
        _log(msg, player)
        return msg

    root = next((r for r in _ROOTS if r.exists()), None)
    if root is None:
        msg = "Sir, I couldn't find a projects folder to search."
        _log(msg, player)
        return msg

    folder = _find_project_folder(root, name)
    if folder is None:
        msg = f"Sir, I couldn't find a project folder matching '{name}' under {root}."
        _log(msg, player)
        return msg

    script = _find_start_script(folder)
    if script is None:
        msg = f"Sir, I found '{folder.name}' but no obvious start script (.bat/.command/main.py) inside it."
        _log(msg, player)
        return msg

    try:
        _launch(script)
    except Exception as e:
        msg = f"Sir, I found '{script.name}' but launching it failed: {e}"
        _log(msg, player)
        return msg

    msg = f"Launching '{folder.name}' via {script.name}."
    _log(msg, player)
    return msg


def _find_project_folder(root: Path, name: str) -> Path | None:
    name_lower = name.lower().replace(" ", "")
    candidates = []
    try:
        entries = list(root.iterdir())
    except Exception:
        return None
    for entry in entries:
        if not entry.is_dir() or entry.name in _IGNORE_DIRS or entry.name.startswith("."):
            continue
        folder_lower = entry.name.lower().replace(" ", "").replace("_", "").replace("-", "")
        if name_lower.replace("_", "").replace("-", "") in folder_lower:
            candidates.append(entry)
    if not candidates:
        return None
    candidates.sort(key=lambda p: len(p.name))
    return candidates[0]


def _find_start_script(folder: Path) -> Path | None:
    folder_words = set(re.findall(r"[a-z0-9]+", folder.name.lower()))
    for pattern in _SCRIPT_PRIORITY:
        matches = sorted(folder.glob(pattern))
        if not matches:
            continue
        # Prefer a script whose name shares words with the folder itself
        # (e.g. "WhatsApp Exporter.bat" over an unrelated "check_bluetooth.bat"
        # that happens to sort first) — plain alphabetical order otherwise.
        named_matches = [
            m for m in matches
            if set(re.findall(r"[a-z0-9]+", m.stem.lower())) & folder_words
        ]
        return named_matches[0] if named_matches else matches[0]
    return None


def _launch(script: Path) -> None:
    if script.suffix.lower() == ".bat":
        subprocess.Popen(["cmd", "/c", "start", "", str(script)], cwd=str(script.parent), shell=False)
    elif script.suffix.lower() == ".command":
        subprocess.Popen(["open", str(script)], cwd=str(script.parent))
    elif script.suffix.lower() == ".py":
        subprocess.Popen([sys.executable, str(script)], cwd=str(script.parent))
    else:
        subprocess.Popen([str(script)], cwd=str(script.parent), shell=True)


def _log(message: str, player=None) -> None:
    print(f"[ProjectLauncher] {message[:200]}")
    if player:
        try:
            player.write_log(f"JARVIS: {message}")
        except Exception:
            pass
