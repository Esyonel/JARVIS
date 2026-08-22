"""
Unattended daily self-improvement run for JARVIS.

Once a day (via Windows Task Scheduler), JARVIS:
  1. Health-checks itself (compile + plugin load + git state).
  2. Asks Gemini for ONE new capability it doesn't have yet, based on the
     plugins it already has, so ideas don't repeat.
  3. Writes it through the normal self_improve path — git checkpoint first,
     syntax + plugin-schema validation after, automatic revert on failure.
  4. Pushes to GitHub only if everything validated.
  5. Appends the outcome to evolution.log either way.

Guardrails for running with nobody watching:
  - Only NEW files under plugins/ (autonomous=True) — never edits main.py,
    ui.py or core/, so a bad unattended change can't stop JARVIS booting.
  - Nothing is pushed unless it compiled AND loaded as a valid plugin.
  - Every run is logged with its result, so a bad streak is visible.
  - Aborts if the working tree has uncommitted changes it didn't create,
    so it never sweeps your in-progress edits into an automatic commit.

Run manually:  .venv\\Scripts\\python.exe daily_evolution.py
"""

import subprocess
import sys
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
LOG_PATH = BASE_DIR / "evolution.log"
sys.path.insert(0, str(BASE_DIR))


def log(message: str) -> None:
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{stamp}] {message}"
    print(line, flush=True)
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def git(args: list[str]) -> tuple[int, str]:
    proc = subprocess.run(
        ["git", *args], cwd=str(BASE_DIR), capture_output=True, text=True, timeout=120,
    )
    return proc.returncode, (proc.stdout + proc.stderr).strip()


def existing_capabilities() -> list[str]:
    from core.plugin_loader import discover_plugins
    registry = discover_plugins(BASE_DIR / "plugins", core_tool_names=set(), logger=lambda _m: None)
    return [f"{r.name}: {r.description[:110]}" for r in registry._all_records if r.valid]


def propose_new_capability(existing: list[str]) -> str:
    from core.ai_text import generate

    listing = "\n".join(f"- {c}" for c in existing)
    prompt = (
        "You are JARVIS, a Turkish-speaking voice assistant running on its owner's "
        "Windows PC. The owner is a systems/network specialist who works with Excel "
        "spreadsheets, runs trading bots, and manages construction projects in "
        "Kazakhstan.\n\n"
        f"Capabilities you ALREADY have:\n{listing}\n\n"
        "Propose exactly ONE genuinely useful NEW capability you do not have yet. "
        "It must not duplicate anything above.\n\n"
        "HARD CONSTRAINT — the plugin may import ONLY these, nothing else:\n"
        "  Python standard library, requests, openpyxl, psutil, numpy, "
        "beautifulsoup4, pillow.\n"
        "Nothing may be pip-installed to make it work. If the feature would need "
        "any other package (speedtest-cli, pandas, matplotlib, scapy, selenium, ...), "
        "propose a DIFFERENT feature instead — a plugin that reports 'library not "
        "found' is worse than useless.\n\n"
        "Reply with ONE sentence in Turkish describing the feature to build. "
        "No preamble, no markdown, just the sentence."
    )
    return generate(prompt).strip('"')


def main() -> int:
    log("=" * 60)
    log("Günlük evrim çalışması başladı.")

    code, dirty = git(["status", "--porcelain"])
    if code != 0:
        log(f"DURDU: git durumu okunamadı — {dirty}")
        return 1
    if dirty.strip():
        log(f"DURDU: kaydedilmemiş {len(dirty.splitlines())} değişiklik var — "
            "kendi commit'ime karıştırmamak için bugün atlıyorum.")
        return 0

    try:
        from plugins.self_evolution import run as health_check
        log("Sağlık kontrolü: " + health_check({}))
    except Exception as e:
        log(f"Sağlık kontrolü başarısız (devam ediliyor): {e}")

    try:
        existing = existing_capabilities()
        idea = propose_new_capability(existing)
        log(f"Yeni yetenek fikri: {idea}")
    except Exception as e:
        log(f"DURDU: yeni yetenek fikri üretilemedi — {e}")
        return 1

    try:
        from plugins.self_improve import run as self_improve
        result = self_improve({"feature_request": idea}, autonomous=True)
        log(f"Uygulama sonucu: {result}")
    except Exception as e:
        log(f"DURDU: değişiklik uygulanamadı — {e}")
        return 1

    # self_improve reverts anything that failed validation, so an unchanged tree
    # here means the attempt was rejected — nothing worth pushing.
    code, out = git(["log", "--oneline", "-1"])
    if code == 0 and "self-improve:" not in out:
        log("Değişiklik uygulanmadı veya geri alındı — push yok.")
        return 0

    code, out = git(["push", "origin", "main"])
    if code == 0:
        log(f"GitHub'a gönderildi: {out.splitlines()[-1] if out else 'ok'}")
    else:
        log(f"GitHub'a gönderilemedi (değişiklik yerelde duruyor): {out}")
        return 1

    log("Günlük evrim tamamlandı.")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # never let the scheduled task die silently
        log(f"BEKLENMEYEN HATA: {type(exc).__name__}: {exc}")
        sys.exit(1)
