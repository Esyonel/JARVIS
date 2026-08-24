"""
JARVIS plugin — code intelligence via the codebase-memory-mcp knowledge graph.

Searches an indexed codebase's functions/classes/call-structure using DeusData's
codebase-memory-mcp CLI (https://github.com/DeusData/codebase-memory-mcp).
Defaults to JARVIS's own source under D:/nu/JARVIS; any other project folder
under D:/nu can be named explicitly. Auto-indexes a project on first use.
Read-only — never writes code or touches git.
"""

import json
import shutil
import subprocess
from pathlib import Path

PLUGIN = {
    "name": "codebase_intelligence",
    "description": (
        "Searches a project's code structure — functions, classes, call "
        "relationships — via the codebase-memory-mcp knowledge graph. Defaults "
        "to JARVIS's own source code. Use for: 'JARVIS'te X fonksiyonu nerede', "
        "'plugin sistemi nasıl çalışıyor', 'bu proje ne yapıyor', 'find function "
        "X', 'kod tabanında Y ara'. NOT for git status/diffs (use git_summary) "
        "and NOT for writing/generating new code (use code_helper)."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "query": {
                "type": "STRING",
                "description": "Natural-language or keyword search, e.g. 'plugin discovery' or 'voice ID enrollment'.",
            },
            "project_name": {
                "type": "STRING",
                "description": "Project folder name under D:/nu to search (e.g. 'Borsa_botu'). Omit to search JARVIS's own code.",
            },
        },
        "required": ["query"],
    },
}

_ROOTS = [Path("D:/nu"), Path.home()]
_CBM_CANDIDATES = [
    Path("D:/nu/codebase-memory-mcp/codebase-memory-mcp.exe"),
]


def _cbm_binary() -> str | None:
    for c in _CBM_CANDIDATES:
        if c.exists():
            return str(c)
    return shutil.which("codebase-memory-mcp")


def _find_repo(project_name: str) -> Path | None:
    name_lower = project_name.lower().replace(" ", "").replace("_", "").replace("-", "")
    root = next((r for r in _ROOTS if r.exists()), None)
    if root is None:
        return None
    try:
        for entry in root.iterdir():
            if not entry.is_dir():
                continue
            folder_lower = entry.name.lower().replace(" ", "").replace("_", "").replace("-", "")
            if name_lower in folder_lower:
                return entry
    except Exception:
        return None
    return None


def _cli(binary: str, tool: str, flags: dict, timeout: int = 60) -> dict:
    cmd = [binary, "cli", "--json", tool]
    for key, value in flags.items():
        cmd.append(f"--{key}")
        cmd.append("true" if value is True else "false" if value is False else str(value))
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    if not result.stdout.strip():
        raise RuntimeError((result.stderr.strip().splitlines() or ["no output"])[-1][:200])
    payload = json.loads(result.stdout.strip())
    data = payload.get("structuredContent", {})
    if payload.get("isError"):
        raise RuntimeError(data.get("error") or data.get("hint") or "tool error")
    return data


def _ensure_indexed(binary: str, repo: Path) -> str:
    repo_str = str(repo).replace("\\", "/").rstrip("/")
    projects = _cli(binary, "list_projects", {}).get("projects", [])
    for p in projects:
        if str(p.get("root_path", "")).replace("\\", "/").rstrip("/") == repo_str:
            return p["name"]
    result = _cli(binary, "index_repository", {"repo-path": repo_str, "mode": "moderate"}, timeout=300)
    return result["project"]


def run(parameters: dict, player=None, session_memory=None) -> str:
    query = (parameters.get("query") or "").strip()
    project_name = (parameters.get("project_name") or "JARVIS").strip()
    if not query:
        msg = "Sir, I need something to search for."
        _log(msg, player)
        return msg

    binary = _cbm_binary()
    if not binary:
        msg = "Sir, codebase-memory-mcp is not installed."
        _log(msg, player)
        return msg

    repo = _find_repo(project_name)
    if repo is None:
        msg = f"Sir, I couldn't find a project folder matching '{project_name}'."
        _log(msg, player)
        return msg

    try:
        project_id = _ensure_indexed(binary, repo)
        data = _cli(binary, "search_graph", {
            "project": project_id, "query": query, "limit": 8, "format": "json",
        })
    except Exception as e:
        msg = f"Sir, the code search failed: {e}"
        _log(msg, player)
        return msg

    rows = data.get("rows", [])
    if not rows:
        msg = f"'{repo.name}' içinde '{query}' ile ilgili bir şey bulamadım."
        _log(msg, player)
        return msg

    cols = data.get("cols", [])
    idx = {c: i for i, c in enumerate(cols)}
    qn_i, label_i, file_i, lines_i = idx.get("qn", 0), idx.get("label", 1), idx.get("file", 2), idx.get("lines", 3)

    highlights = []
    for r in rows[:5]:
        name = str(r[qn_i]).split(".")[-1]
        highlights.append(f"{r[label_i]} {name} ({r[file_i]}:{r[lines_i]})")

    total = data.get("total", len(rows))
    summary = (
        f"'{repo.name}' içinde '{query}' için {total} sonuç buldum. "
        f"En iyileri: {'; '.join(highlights)}."
    )
    _log(summary, player)
    return summary[:2500]


def _log(message: str, player=None) -> None:
    print(f"[CodebaseIntelligence] {message[:200]}")
    if player:
        try:
            player.write_log(f"JARVIS: {message}")
        except Exception:
            pass
