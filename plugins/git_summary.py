"""
JARVIS plugin — git status/diff summary for a project.

Runs `git status` + `git diff --stat` in a project folder and turns the raw
output into a short spoken summary ("neyi değiştirmiştim" / "what did I
change"). Read-only — never commits, stages, or pushes anything.
"""

import subprocess
from pathlib import Path

PLUGIN = {
    "name": "git_summary",
    "description": (
        "Summarizes uncommitted git changes in a project folder — which "
        "files were modified/added/deleted, and roughly how much. Use for: "
        "'şu projede neyi değiştirmiştim', 'what did I change in the trading "
        "bot', 'hangi dosyalar değişti'. Read-only — never stages, commits, "
        "or pushes anything."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "project_name": {
                "type": "STRING",
                "description": "Project folder name to check (e.g. 'Borsa_botu'). Must be a git repository.",
            },
        },
        "required": ["project_name"],
    },
}

_ROOTS = [Path("D:/nu"), Path.home()]


def run(parameters: dict, player=None, session_memory=None) -> str:
    project_name = (parameters.get("project_name") or "").strip()
    if not project_name:
        msg = "Sir, I need a project name to check."
        _log(msg, player)
        return msg

    repo = _find_repo(project_name)
    if repo is None:
        msg = f"Sir, I couldn't find a git repository matching '{project_name}'."
        _log(msg, player)
        return msg

    try:
        branch = _run_git(repo, ["rev-parse", "--abbrev-ref", "HEAD"]).strip()
        status = _run_git(repo, ["status", "--porcelain"])
        diffstat = _run_git(repo, ["diff", "--stat"])
    except Exception as e:
        msg = f"Sir, git failed in '{repo.name}': {e}"
        _log(msg, player)
        return msg

    result = _summarize(repo.name, branch, status, diffstat)
    _log(result, player)
    return result


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
            if name_lower in folder_lower and (entry / ".git").exists():
                return entry
    except Exception:
        return None
    return None


def _run_git(repo: Path, args: list[str]) -> str:
    result = subprocess.run(
        ["git", *args], cwd=str(repo), capture_output=True, text=True, timeout=15,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "git command failed")
    return result.stdout


def _summarize(name: str, branch: str, status: str, diffstat: str) -> str:
    lines = [l for l in status.splitlines() if l.strip()]
    if not lines:
        return f"'{name}' ({branch} dalı): temiz, kaydedilmemiş değişiklik yok."

    modified = sum(1 for l in lines if l.startswith(" M") or l.startswith("M"))
    added = sum(1 for l in lines if l.startswith("A") or l.startswith("??"))
    deleted = sum(1 for l in lines if l.startswith(" D") or l.startswith("D"))

    files_preview = ", ".join(l[3:].strip() for l in lines[:8])
    more = f" ve {len(lines) - 8} dosya daha" if len(lines) > 8 else ""

    summary = (
        f"'{name}' ({branch} dalı): {len(lines)} dosya değişmiş "
        f"({modified} düzenlenmiş, {added} yeni, {deleted} silinmiş). "
        f"Dosyalar: {files_preview}{more}."
    )

    stat_summary = diffstat.strip().splitlines()[-1] if diffstat.strip() else ""
    if stat_summary:
        summary += f" {stat_summary.strip()}"

    return summary[:2500]


def _log(message: str, player=None) -> None:
    print(f"[GitSummary] {message[:200]}")
    if player:
        try:
            player.write_log(f"JARVIS: {message}")
        except Exception:
            pass
