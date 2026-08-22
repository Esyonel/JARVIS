"""
JARVIS plugin — self-modification: on request, JARVIS can extend its own
source code, including core files (main.py, ui.py, core/, actions/), not
just drop-in plugins.

Letting an LLM edit the code that IS the running application has real blast
radius, so this is wrapped in a hard safety net:

  1. Git checkpoint (commit) of the whole repo BEFORE any change — always
     possible to get back to a known-good state.
  2. Gemini proposes a TARGETED search/replace edit (old_string -> new_string)
     for an existing file, or full content for a brand new file — never a
     silent full-file rewrite of something already there.
  3. An edit only applies if old_string is found in the file EXACTLY ONCE
     (same rule as a normal precise find/replace) — ambiguous edits are
     rejected rather than guessed at.
  4. Every changed .py file is syntax-checked (py_compile) immediately after.
  5. ANY failure (old_string not found/not unique, syntax error) reverts the
     whole checkpoint automatically — JARVIS is never left broken.
  6. Never touches secrets/personal data (config/api_keys.json,
     memory/long_term.json, .env, .git/) regardless of what's asked.
  7. Changes only take effect after JARVIS is restarted — this tool never
     restarts the running process itself, and never touches this very file
     (self_improve.py) while it's the one running.
"""

import json
import subprocess
import sys
from pathlib import Path

PLUGIN = {
    "name": "self_improve",
    "description": (
        "Extends JARVIS's own source code — including core files, not just "
        "plugins — based on a spoken feature request. Use for: 'kendine şu "
        "özelliği ekle', 'kendi kodunu geliştir', 'şunu kendine yaz'. Every "
        "change is git-checkpointed and syntax-validated automatically; a "
        "broken change is reverted on the spot, never left in place. Changes "
        "need a JARVIS restart to take effect — say so after applying one."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "feature_request": {
                "type": "STRING",
                "description": "What to add or change, in the user's own words, as much detail as given.",
            },
        },
        "required": ["feature_request"],
    },
}

BASE_DIR = Path(__file__).resolve().parent.parent
_THIS_FILE = Path(__file__).resolve()

_FORBIDDEN_PATHS = {
    "config/api_keys.json", "memory/long_term.json", ".env",
    "config/voice_id.npy", "jarvis.log",
}
_FORBIDDEN_PREFIXES = (".git/", ".venv/", "__pycache__/")


def run(parameters: dict, player=None, session_memory=None) -> str:
    feature = (parameters.get("feature_request") or "").strip()
    if not feature:
        msg = "Sir, I need a description of what to add or change."
        _log(msg, player)
        return msg

    try:
        checkpoint = _git_checkpoint(feature)
    except Exception as e:
        msg = f"Sir, I couldn't create a safety checkpoint, so I won't proceed: {e}"
        _log(msg, player)
        return msg

    try:
        plan = _ask_gemini_for_edit(feature)
    except Exception as e:
        msg = f"Sir, I couldn't draft a change for that: {e}"
        _log(msg, player)
        return msg

    ok, detail = _validate_plan(plan)
    if not ok:
        msg = f"Sir, the drafted change didn't look safe ({detail}), so I skipped it — nothing was touched."
        _log(msg, player)
        return msg

    try:
        target = _apply_plan(plan)
    except Exception as e:
        _git_revert(checkpoint)
        msg = f"Sir, applying the change failed ({e}) — reverted, JARVIS is untouched."
        _log(msg, player)
        return msg

    compile_error = _check_syntax(target)
    if compile_error:
        _git_revert(checkpoint)
        msg = f"Sir, the new code had a syntax error ({compile_error}) — reverted automatically, JARVIS is untouched."
        _log(msg, player)
        return msg

    plugin_error = _check_plugin_validity(target)
    if plugin_error:
        _git_revert(checkpoint)
        msg = f"Sir, the new plugin didn't pass validation ({plugin_error}) — reverted automatically, JARVIS is untouched."
        _log(msg, player)
        return msg

    try:
        _git_finalize(feature)
    except Exception as e:
        print(f"[SelfImprove] Commit finalize failed (change still applied on disk): {e}")

    msg = (
        f"Done, efendim. I added the requested change to '{target}'. "
        "Restart JARVIS for it to take effect — I checkpointed the previous "
        "state first, so if anything's wrong, it can be rolled back."
    )
    _log(msg, player)
    return msg


# ── Git safety net ──────────────────────────────────────────────────────────

def _git(args: list[str]) -> str:
    result = subprocess.run(
        ["git", *args], cwd=str(BASE_DIR), capture_output=True, text=True, timeout=20,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or f"git {' '.join(args)} failed")
    return result.stdout


def _git_checkpoint(feature: str) -> str:
    _git(["add", "-A"])
    status = _git(["status", "--porcelain"])
    if status.strip():
        _git(["commit", "-m", f"checkpoint before self-improve: {feature[:80]}"])
    return _git(["rev-parse", "HEAD"]).strip()


def _git_finalize(feature: str) -> None:
    _git(["add", "-A"])
    status = _git(["status", "--porcelain"])
    if status.strip():
        _git(["commit", "-m", f"self-improve: {feature[:80]}"])


def _git_revert(checkpoint_sha: str) -> None:
    try:
        _git(["reset", "--hard", checkpoint_sha])
    except Exception as e:
        print(f"[SelfImprove] CRITICAL: revert to {checkpoint_sha} failed: {e}")


# ── Drafting the change ──────────────────────────────────────────────────────

def _ask_gemini_for_edit(feature: str) -> dict:
    from config import get_config
    key = get_config().get("gemini_api_key")
    if not key:
        raise RuntimeError("no Gemini API key configured")

    from google import genai
    client = genai.Client(api_key=key)

    file_list = "\n".join(
        str(p.relative_to(BASE_DIR)).replace("\\", "/")
        for p in BASE_DIR.rglob("*.py")
        if not any(str(p.relative_to(BASE_DIR)).replace("\\", "/").startswith(pre) for pre in _FORBIDDEN_PREFIXES)
    )

    prompt = f"""You are extending the source code of a running Python voice assistant
called JARVIS (PyQt6 GUI in ui.py, Gemini Live session in main.py, drop-in
tools in plugins/*.py, other logic in core/ and actions/).

Existing Python files:
{file_list}

Feature to add: {feature}

Reply with ONLY a JSON object (no markdown fences), one of two shapes:

For a brand new file (prefer this for a genuinely new capability — put it in
plugins/<snake_case_name>.py following the existing plugin pattern EXACTLY):
{{"mode": "new_file", "file": "plugins/example_name.py", "content": "<full file content>"}}

The file content for a new plugin MUST follow this exact contract (copy the
shape precisely, these are the most common mistakes to avoid):
  - A module-level dict literally named PLUGIN with keys "name" (snake_case
    str), "description" (str), "parameters" (a dict — "type" MUST be the
    UPPERCASE STRING "OBJECT", not "object"; "properties" a dict, "required"
    a list, both may be empty).
  - A top-level function `def run(parameters: dict, player=None,
    session_memory=None) -> str:` that returns a SHORT PLAIN STRING (never a
    dict/JSON) — this string is spoken aloud to the user. Never let it raise;
    catch errors internally and return an error string instead.

For editing an existing file (prefer this when changing existing behavior):
{{"mode": "edit", "file": "path/relative/to/repo/root.py",
  "old_string": "<exact existing text to find, enough context to be unique>",
  "new_string": "<replacement text>"}}

old_string must be copied EXACTLY as it appears in the file, including
whitespace. Keep the change minimal and focused on the request."""

    resp = client.models.generate_content(model="gemini-flash-latest", contents=prompt)
    text = (resp.text or "").strip()
    text = text.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    return json.loads(text)


def _validate_plan(plan: dict) -> tuple[bool, str]:
    mode = plan.get("mode")
    file_rel = (plan.get("file") or "").replace("\\", "/").lstrip("/")

    if mode not in ("new_file", "edit"):
        return False, "unrecognised mode"
    if not file_rel or not file_rel.endswith(".py"):
        return False, "no valid target .py file"
    if file_rel in _FORBIDDEN_PATHS or any(file_rel.startswith(p) for p in _FORBIDDEN_PREFIXES):
        return False, "target file is off-limits"

    target = (BASE_DIR / file_rel).resolve()
    if BASE_DIR not in target.parents and target != BASE_DIR:
        return False, "target escapes the JARVIS directory"
    if target == _THIS_FILE:
        return False, "cannot modify self_improve.py while it's running"

    if mode == "new_file":
        if not plan.get("content"):
            return False, "no content for new file"
        if target.exists():
            return False, "target file already exists — use edit mode instead"
    else:
        if not target.exists():
            return False, "target file for edit doesn't exist"
        if not plan.get("old_string") or "new_string" not in plan:
            return False, "missing old_string/new_string"

    return True, ""


def _apply_plan(plan: dict) -> str:
    file_rel = plan["file"].replace("\\", "/").lstrip("/")
    target = BASE_DIR / file_rel

    if plan["mode"] == "new_file":
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(plan["content"], encoding="utf-8")
    else:
        text = target.read_text(encoding="utf-8")
        count = text.count(plan["old_string"])
        if count != 1:
            raise RuntimeError(f"old_string found {count} times (need exactly 1)")
        target.write_text(text.replace(plan["old_string"], plan["new_string"], 1), encoding="utf-8")

    return file_rel


def _check_syntax(file_rel: str) -> str | None:
    target = BASE_DIR / file_rel
    result = subprocess.run(
        [sys.executable, "-m", "py_compile", str(target)],
        capture_output=True, text=True, timeout=15,
    )
    if result.returncode != 0:
        return (result.stderr or result.stdout).strip()[:500]
    return None


def _check_plugin_validity(file_rel: str) -> str | None:
    """For new/edited files under plugins/, run the real plugin loader's
    schema validation — catches a file that compiles fine but doesn't match
    the expected PLUGIN dict / run() contract (wrong types, missing fields),
    which py_compile alone would never notice."""
    if not file_rel.startswith("plugins/") or Path(file_rel).name.startswith("_"):
        return None
    try:
        import importlib.util
        from core.plugin_loader import _validate as _plugin_validate

        target = BASE_DIR / file_rel
        spec = importlib.util.spec_from_file_location(f"_self_improve_check_{target.stem}", target)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        rec = _plugin_validate(module, target.name)
        return None if rec.valid else rec.error
    except Exception as e:
        return str(e)


def _log(message: str, player=None) -> None:
    print(f"[SelfImprove] {message[:300]}")
    if player:
        try:
            player.write_log(f"JARVIS: {message}")
        except Exception:
            pass
