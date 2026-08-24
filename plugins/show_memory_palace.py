"""JARVIS plugin — opens the codebase-memory-mcp graph UI ("memory palace")
in the default browser. Starts the daemon first if it isn't already running.
"""

import subprocess
import time
import webbrowser

from core.memory_palace import _cbm_binary

_UI_URL = "http://127.0.0.1:9749"

PLUGIN = {
    "name": "show_memory_palace",
    "description": (
        "Opens the memory palace — the indexed knowledge graph of all projects "
        "and past conversations — in the browser on localhost. Use for: "
        "'hafıza sarayını göster', 'hafıza sarayını aç', 'show me the memory "
        "palace', 'bilgi grafiğini göster'."
    ),
    "parameters": {"type": "OBJECT", "properties": {}, "required": []},
}


def run(parameters: dict, player=None, session_memory=None) -> str:
    binary = _cbm_binary()
    if not binary:
        msg = "Sir, codebase-memory-mcp is not installed."
        _log(msg, player)
        return msg

    try:
        status = subprocess.run([binary, "daemon", "status"], capture_output=True, text=True, timeout=15)
        if "active" not in status.stdout.lower():
            subprocess.run([binary, "daemon", "start"], capture_output=True, text=True, timeout=30)
            time.sleep(2)
    except Exception as e:
        msg = f"Sir, I couldn't reach the memory palace server: {e}"
        _log(msg, player)
        return msg

    webbrowser.open(_UI_URL)
    msg = f"Hafıza sarayı açılıyor efendim — {_UI_URL}"
    _log(msg, player)
    return msg


def _log(message: str, player=None) -> None:
    print(f"[MemoryPalace] {message[:200]}")
    if player:
        try:
            player.write_log(f"JARVIS: {message}")
        except Exception:
            pass
