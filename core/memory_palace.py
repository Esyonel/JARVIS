"""Memory palace bootstrap — codebase-memory-mcp as JARVIS's long-term index.

Read-only. Never deletes or modifies anything it scans.

One-time job (guarded by a marker file) that, on JARVIS's first launch after
this feature was added:
  1. Walks the whole C:\\ and D:\\ drives (system/cache/library folders
     pruned) looking for project-like folders and indexes each one into
     codebase-memory-mcp, so their code becomes searchable.
  2. Extracts past Claude Code conversation transcripts (D:/nu session logs)
     into clean per-session markdown files and indexes that folder too.

Separately, an ongoing (not one-time) background watcher indexes any USB /
removable drive as soon as it's plugged in.

After that, plugins/show_memory_palace.py opens the graph UI on demand
(voice: "hafıza sarayını göster"). Nothing here talks to the daemon's MCP
protocol directly — everything goes through `codebase-memory-mcp cli`, same
as plugins/codebase_intelligence.py.
"""

import json
import re
import shutil
import subprocess
import time
from pathlib import Path
from typing import Callable

BASE_DIR         = Path(__file__).resolve().parent.parent          # D:/nu/JARVIS
FULL_SCAN_ROOTS   = [Path("D:/"), Path("C:/")]   # D: first — it's the user's actual workspace
MARKER_PATH       = BASE_DIR / "memory" / ".memory_palace_bootstrapped"
CONV_SRC_DIR      = Path.home() / ".claude" / "projects" / "d--nu"
CONV_DEST_DIR     = BASE_DIR / "memory" / "conversations"
MAX_WALK_DEPTH    = 8
USB_POLL_SECONDS  = 15

_CBM_CANDIDATES = [Path("D:/nu/codebase-memory-mcp/codebase-memory-mcp.exe")]

# Directories that are never real user projects — system, cache, library,
# and sensitive-data folders. Pruned before descending, so C:\ and D:\ scans
# never touch OS files, installed programs, or app caches/credential stores.
_SKIP_DIR_NAMES = {
    "node_modules", "__pycache__", ".venv", "venv", ".git", "dist", "build",
    ".next", ".cache", "codebase-memory-mcp", ".tmp-cbm-install",
    "windows", "program files", "program files (x86)", "programdata",
    "appdata", "$recycle.bin", "system volume information", "recovery",
    "perflogs", "config.msi", "msocache", "intel", "nvidia", "amd",
    "windowsapps", "onedrivetemp",
}
_MARKER_FILES = {
    ".git", "package.json", "requirements.txt", "pyproject.toml",
    "composer.json", "pubspec.yaml", "Cargo.toml", "go.mod", "manage.py",
}

Logger = Callable[[str], None]


def _cbm_binary() -> str | None:
    for c in _CBM_CANDIDATES:
        if c.exists():
            return str(c)
    return shutil.which("codebase-memory-mcp")


def _cli(binary: str, tool: str, flags: dict, timeout: int = 600) -> dict:
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


def ensure_daemon_running(binary: str) -> None:
    try:
        subprocess.run([binary, "daemon", "start"], capture_output=True, text=True, timeout=30)
    except Exception:
        pass


def _should_prune(folder: Path) -> bool:
    name = folder.name.lower()
    return name.startswith(".") or name in _SKIP_DIR_NAMES


def _looks_like_project(folder: Path) -> bool:
    """Marker files only (.git, package.json, requirements.txt, ...) — NOT a
    loose 'any source file present' fallback. That fallback used to match any
    folder with a single .py/.js file in it, which fragments one real project
    (e.g. a printer driver's localized manual, a vendored JS library inside
    node_modules-style resource trees) into dozens of fake sub-projects."""
    if _should_prune(folder):
        return False
    try:
        names = {p.name for p in folder.iterdir()}
    except Exception:
        return False
    return bool(names & _MARKER_FILES)


# D:/nu is itself a git repo at its root, but its *children* (JARVIS,
# Borsa_botu, alivuralenerji, ...) are the real, separately-useful projects —
# so unlike every other matched project root, don't stop here, keep
# descending into its children.
_ALWAYS_DESCEND = {Path("D:/nu")}


def find_project_roots(root: Path, max_depth: int = MAX_WALK_DEPTH) -> list[Path]:
    """Recursively finds project-like folders under root. Stops descending
    once a project root is found (its internals aren't separately indexed)
    and never enters a pruned (system/cache/library) directory."""
    found: list[Path] = []

    def _walk(folder: Path, depth: int) -> None:
        if depth > max_depth or _should_prune(folder):
            return
        if folder not in _ALWAYS_DESCEND and _looks_like_project(folder):
            found.append(folder)
            return
        try:
            children = [c for c in folder.iterdir() if c.is_dir()]
        except Exception:
            return
        for child in children:
            _walk(child, depth + 1)

    try:
        for child in root.iterdir():
            if child.is_dir():
                _walk(child, 1)
    except Exception:
        pass
    return found


def _indexed_root_paths(binary: str) -> set[str]:
    try:
        projects = _cli(binary, "list_projects", {}).get("projects", [])
    except Exception:
        return set()
    return {str(p.get("root_path", "")).replace("\\", "/").rstrip("/") for p in projects}


def index_projects_under(binary: str, root: Path, log: Logger) -> None:
    if not root.exists():
        return
    already = _indexed_root_paths(binary)
    log(f"Hafıza sarayı: '{root}' taranıyor (bu sürebilir)...")
    candidates = find_project_roots(root)
    log(f"Hafıza sarayı: '{root}' altında {len(candidates)} proje bulundu.")
    for folder in candidates:
        repo_str = str(folder).replace("\\", "/").rstrip("/")
        if repo_str in already:
            continue
        try:
            log(f"Hafıza sarayı: '{folder.name}' indexleniyor...")
            _cli(binary, "index_repository", {"repo-path": repo_str, "mode": "fast"}, timeout=600)
        except Exception as e:
            log(f"Hafıza sarayı: '{folder.name}' indexlenemedi: {e}")


def scan_and_index_all_projects(binary: str, log: Logger) -> None:
    for root in FULL_SCAN_ROOTS:
        index_projects_under(binary, root, log)
    log("Hafıza sarayı: C: ve D: sürücü taraması tamamlandı.")


# --- USB / removable drives (ongoing, not one-time) --------------------------

def _existing_drive_letters() -> set[str]:
    import psutil
    return {p.device[:2].upper() for p in psutil.disk_partitions(all=False)}


def watch_for_usb_drives(binary: str, log: Logger) -> None:
    """Runs for the life of the process. Any drive letter that appears after
    startup (a USB stick, external HDD, phone in MTP mode, etc.) gets scanned
    for project-like folders and indexed the same way as C:/D:. Read-only —
    never writes to or deletes anything on the drive."""
    known = _existing_drive_letters()
    while True:
        try:
            current = _existing_drive_letters()
            new_drives = current - known
            for letter in new_drives:
                root = Path(f"{letter}\\")
                log(f"Hafıza sarayı: yeni sürücü tespit edildi ({letter}), taranıyor...")
                try:
                    index_projects_under(binary, root, log)
                    log(f"Hafıza sarayı: '{letter}' sürücüsü tarandı.")
                except Exception as e:
                    log(f"Hafıza sarayı: '{letter}' sürücüsü taranamadı: {e}")
            known = current
        except Exception:
            pass
        time.sleep(USB_POLL_SECONDS)


# --- conversation export -----------------------------------------------------

def _extract_text(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                text = block.get("text", "").strip()
                if text:
                    parts.append(text)
        return "\n".join(parts)
    return ""


_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}")


def _export_session(jsonl_path: Path, dest_dir: Path) -> Path | None:
    turns = []
    date = ""
    try:
        with jsonl_path.open(encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except Exception:
                    continue
                etype = entry.get("type")
                if etype not in ("user", "assistant"):
                    continue
                if not date:
                    ts = entry.get("timestamp", "")
                    m = _DATE_RE.match(ts)
                    if m:
                        date = m.group(0)
                text = _extract_text(entry.get("message", {}).get("content"))
                if text:
                    speaker = "Kullanıcı" if etype == "user" else "Claude"
                    turns.append(f"## {speaker}\n\n{text}\n")
    except Exception:
        return None

    if not turns:
        return None

    date = date or "0000-00-00"
    out_path = dest_dir / f"{date}_{jsonl_path.stem[:8]}.md"
    out_path.write_text(
        f"# Konuşma — {date} (session {jsonl_path.stem[:8]})\n\n" + "\n".join(turns),
        encoding="utf-8",
    )
    return out_path


def export_conversations(log: Logger) -> Path | None:
    if not CONV_SRC_DIR.exists():
        return None
    CONV_DEST_DIR.mkdir(parents=True, exist_ok=True)
    jsonl_files = sorted(CONV_SRC_DIR.glob("*.jsonl"))
    log(f"Hafıza sarayı: {len(jsonl_files)} önceki konuşma bulundu, işleniyor...")
    written = 0
    for jsonl_path in jsonl_files:
        out_path = CONV_DEST_DIR / f"*_{jsonl_path.stem[:8]}.md"
        if list(CONV_DEST_DIR.glob(out_path.name)):
            continue
        try:
            if _export_session(jsonl_path, CONV_DEST_DIR):
                written += 1
        except Exception as e:
            log(f"Hafıza sarayı: konuşma işlenemedi ({jsonl_path.name}): {e}")
    log(f"Hafıza sarayı: {written} yeni konuşma dosyası yazıldı.")
    return CONV_DEST_DIR if any(CONV_DEST_DIR.iterdir()) else None


def index_conversations(binary: str, log: Logger) -> None:
    conv_dir = export_conversations(log)
    if conv_dir is None:
        return
    repo_str = str(conv_dir).replace("\\", "/").rstrip("/")
    already = _indexed_root_paths(binary)
    if repo_str in already:
        try:
            log("Hafıza sarayı: konuşma arşivi yeniden indexleniyor...")
            _cli(binary, "index_repository", {"repo-path": repo_str, "mode": "fast"}, timeout=600)
        except Exception as e:
            log(f"Hafıza sarayı: konuşma arşivi indexlenemedi: {e}")
        return
    try:
        log("Hafıza sarayı: konuşma arşivi indexleniyor...")
        _cli(binary, "index_repository", {"repo-path": repo_str, "mode": "fast"}, timeout=600)
    except Exception as e:
        log(f"Hafıza sarayı: konuşma arşivi indexlenemedi: {e}")


# --- entry point --------------------------------------------------------------

def run_first_boot_bootstrap(log: Logger = print) -> None:
    """Runs once, ever — safe to call on every startup, no-ops after the
    first successful run. Call from a background daemon thread."""
    if MARKER_PATH.exists():
        return
    binary = _cbm_binary()
    if not binary:
        log("Hafıza sarayı: codebase-memory-mcp bulunamadı, atlanıyor.")
        return
    try:
        ensure_daemon_running(binary)
        scan_and_index_all_projects(binary, log)
        index_conversations(binary, log)
        MARKER_PATH.parent.mkdir(parents=True, exist_ok=True)
        MARKER_PATH.write_text("done", encoding="utf-8")
        log("Hafıza sarayı: kurulum tamamlandı. 'Hafıza sarayını göster' diyerek açabilirsin.")
    except Exception as e:
        log(f"Hafıza sarayı: kurulum sırasında hata: {e}")
