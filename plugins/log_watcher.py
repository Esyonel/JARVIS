"""
JARVIS plugin — check a project's log file for recent errors.

On-demand snapshot (not a background daemon — a single Live tool call must
return fast, so this never blocks/polls). Finds the most recently modified
*.log file for a project (or a given path), reads its tail, and reports any
ERROR/CRITICAL/Traceback lines found near the end, with the most recent one
shown in full. Ask again any time for a fresh check.
"""

import re
from pathlib import Path

PLUGIN = {
    "name": "log_watcher",
    "description": (
        "Checks a running project's log file for recent errors right now "
        "(ERROR/CRITICAL lines, Python tracebacks). Use for: 'Borsa botunun "
        "loglarında hata var mı', 'check the trading bot's log for errors', "
        "'kripto botu çöktü mü'. This is a snapshot check, not continuous "
        "monitoring — ask again any time for an updated check. Give the "
        "project folder name, or a direct path to a .log file."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "project_name": {
                "type": "STRING",
                "description": "Project folder name to search for a .log file in (e.g. 'Borsa_botu').",
            },
            "log_path": {
                "type": "STRING",
                "description": "Direct path to a specific log file, if known. Overrides project_name.",
            },
        },
        "required": [],
    },
}

_ROOTS = [Path("D:/nu"), Path.home()]
_TAIL_BYTES = 60_000
_ERROR_RE = re.compile(r"\b(ERROR|CRITICAL|EXCEPTION|TRACEBACK|FATAL)\b", re.IGNORECASE)


def run(parameters: dict, player=None, session_memory=None) -> str:
    project_name = (parameters.get("project_name") or "").strip()
    log_path = (parameters.get("log_path") or "").strip()

    try:
        if log_path:
            path = Path(log_path).expanduser()
            if not path.exists():
                msg = f"Sir, no log file found at '{log_path}'."
                _log(msg, player)
                return msg
        elif project_name:
            path = _find_log(project_name)
            if path is None:
                msg = f"Sir, I couldn't find a .log file for a project matching '{project_name}'."
                _log(msg, player)
                return msg
        else:
            msg = "Sir, I need a project name or a log file path to check."
            _log(msg, player)
            return msg

        tail = _read_tail(path, _TAIL_BYTES)
    except Exception as e:
        msg = f"Sir, I couldn't read the log file: {e}"
        _log(msg, player)
        return msg

    result = _summarize(path, tail)
    _log(result, player)
    return result


def _find_log(project_name: str) -> Path | None:
    name_lower = project_name.lower().replace(" ", "").replace("_", "").replace("-", "")
    root = next((r for r in _ROOTS if r.exists()), None)
    if root is None:
        return None

    project_dir = None
    try:
        for entry in root.iterdir():
            if not entry.is_dir():
                continue
            folder_lower = entry.name.lower().replace(" ", "").replace("_", "").replace("-", "")
            if name_lower in folder_lower:
                project_dir = entry
                break
    except Exception:
        return None
    if project_dir is None:
        return None

    logs = sorted(project_dir.rglob("*.log"), key=lambda p: p.stat().st_mtime, reverse=True)
    return logs[0] if logs else None


def _read_tail(path: Path, max_bytes: int) -> str:
    size = path.stat().st_size
    with open(path, "rb") as f:
        if size > max_bytes:
            f.seek(size - max_bytes)
        data = f.read()
    return data.decode("utf-8", errors="replace")


def _summarize(path: Path, tail: str) -> str:
    lines = tail.splitlines()
    error_lines = [(i, l) for i, l in enumerate(lines) if _ERROR_RE.search(l)]

    if not error_lines:
        return f"'{path.name}': son kayıtlarda hata görünmüyor, temiz."

    last_idx, last_line = error_lines[-1]
    context = "\n".join(lines[max(0, last_idx - 2): last_idx + 3])
    return (
        f"'{path.name}': son kayıtlarda {len(error_lines)} hata satırı bulundu. "
        f"En sonuncusu:\n{context}"[:2500]
    )


def _log(message: str, player=None) -> None:
    print(f"[LogWatcher] {message[:200]}")
    if player:
        try:
            player.write_log(f"JARVIS: {message}")
        except Exception:
            pass
