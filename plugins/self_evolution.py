"""
JARVIS plugin — real self-diagnostics (system health check).

This file was originally auto-written by JARVIS itself via self_improve, but
it only *claimed* to do work: it returned "self-improvement cycle completed
successfully" while doing nothing but counting files, and its "update_system"
branch ran a bare `git pull` that could clobber uncommitted local work. Both
were replaced with checks that actually run and report what they really find.

For genuinely ADDING new capabilities/code, this is NOT the tool — that's
self_improve, which drafts a real code change, validates it, and can revert.
"""

import subprocess
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

PLUGIN = {
    "name": "self_evolution",
    "description": (
        "Runs a real self-diagnostic health check on JARVIS: verifies every "
        "Python file still compiles, counts loadable vs. broken plugins, and "
        "reports uncommitted changes. Reports what it ACTUALLY finds, including "
        "failures. Use for: 'kendini kontrol et', 'sistem sağlığın nasıl', "
        "'bir sorunun var mı', 'kendini test et'. This tool only INSPECTS — to "
        "actually add a new feature or change code, use self_improve instead."
    ),
    "parameters": {"type": "OBJECT", "properties": {}, "required": []},
}


def run(parameters: dict, player=None, session_memory=None) -> str:
    findings = []

    syntax_bad = _check_all_syntax()
    if syntax_bad:
        findings.append(f"{len(syntax_bad)} dosyada sözdizimi hatası var: {', '.join(syntax_bad[:5])}")
    else:
        findings.append("Tüm Python dosyaları hatasız derleniyor")

    ok_count, broken = _check_plugins()
    if broken:
        findings.append(f"{ok_count} eklenti çalışıyor, {len(broken)} tanesi bozuk: {', '.join(broken)}")
    else:
        findings.append(f"{ok_count} eklentinin hepsi sorunsuz yükleniyor")

    dirty = _check_git_dirty()
    if dirty is None:
        findings.append("git durumu okunamadı")
    elif dirty:
        findings.append(f"{dirty} dosyada kaydedilmemiş değişiklik var")
    else:
        findings.append("kaydedilmemiş değişiklik yok")

    result = "Sistem kontrolü: " + ". ".join(findings) + "."
    _log(result, player)
    return result


def _check_all_syntax() -> list[str]:
    """Returns the names of files that fail to compile (empty list = all good)."""
    bad = []
    for path in BASE_DIR.rglob("*.py"):
        rel = str(path.relative_to(BASE_DIR)).replace("\\", "/")
        if rel.startswith((".venv/", "__pycache__/", ".git/")):
            continue
        proc = subprocess.run(
            [sys.executable, "-m", "py_compile", str(path)],
            capture_output=True, text=True, timeout=20,
        )
        if proc.returncode != 0:
            bad.append(path.name)
    return bad


def _check_plugins() -> tuple[int, list[str]]:
    """Returns (working_count, [names of broken plugins]) using the real loader."""
    try:
        from core.plugin_loader import discover_plugins
        registry = discover_plugins(BASE_DIR / "plugins", core_tool_names=set(), logger=lambda _m: None)
        broken = [r.name for r in registry._all_records if not r.valid]
        return len(registry._plugins), broken
    except Exception as e:
        return 0, [f"tarama başarısız: {e}"]


def _check_git_dirty() -> int | None:
    """Returns the count of uncommitted changes, or None if git isn't readable."""
    try:
        proc = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=str(BASE_DIR), capture_output=True, text=True, timeout=15,
        )
        if proc.returncode != 0:
            return None
        return len([ln for ln in proc.stdout.splitlines() if ln.strip()])
    except Exception:
        return None


def _log(message: str, player=None) -> None:
    print(f"[SelfEvolution] {message[:300]}")
    if player:
        try:
            player.write_log(f"JARVIS: {message}")
        except Exception:
            pass
