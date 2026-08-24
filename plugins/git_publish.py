"""JARVIS plugin — publish its validated source changes to GitHub."""

import subprocess
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
PROTECTED_PATHS = {
    "memory/api_usage.json",
    "memory/device_snapshot.json",
}

PLUGIN = {
    "name": "git_publish",
    "description": (
        "Publishes JARVIS source changes to its configured GitHub repository. "
        "Use only when the owner explicitly asks JARVIS to send or publish "
        "itself; stages non-ignored files, excludes runtime state, commits, "
        "and pushes to origin/main."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "message": {
                "type": "STRING",
                "description": "Optional commit message.",
            },
        },
        "required": [],
    },
}


def _git(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=str(BASE_DIR),
        capture_output=True,
        text=True,
        timeout=120,
    )


def run(parameters: dict, player=None, session_memory=None) -> str:
    message = (parameters.get("message") or "JARVIS: source update").strip()
    if not message:
        message = "JARVIS: source update"

    status = _git(["status", "--porcelain"])
    if status.returncode != 0:
        return _result("Git durumu okunamadı", player)
    if not status.stdout.strip():
        return _result("JARVIS deposu zaten temiz; gönderilecek değişiklik yok", player)

    add = _git(["add", "-A"])
    if add.returncode != 0:
        return _result(f"Dosyalar hazırlığa alınamadı: {_error(add)}", player)

    reset = _git(["reset", "--", *sorted(PROTECTED_PATHS)])
    if reset.returncode != 0:
        _git(["reset"])
        return _result(f"Çalışma zamanı dosyaları ayrılamadı: {_error(reset)}", player)

    staged = _git(["diff", "--cached", "--name-only"])
    if staged.returncode != 0 or not staged.stdout.strip():
        _git(["reset"])
        return _result("Gönderilecek kaynak değişikliği bulunamadı", player)

    commit = _git(["commit", "-m", message])
    if commit.returncode != 0:
        _git(["reset"])
        return _result(f"Commit oluşturulamadı: {_error(commit)}", player)

    push = _git(["push", "origin", "main"])
    if push.returncode != 0:
        return _result(
            f"Commit oluşturuldu ancak GitHub'a gönderilemedi: {_error(push)}",
            player,
        )

    return _result("JARVIS kaynakları başarıyla GitHub'a gönderildi", player)


def _error(result: subprocess.CompletedProcess[str]) -> str:
    return (result.stderr or result.stdout).strip()[-500:]


def _result(message: str, player=None) -> str:
    print(f"[GitPublish] {message}")
    if player:
        try:
            player.write_log(f"JARVIS: {message}")
        except Exception:
            pass
    return message