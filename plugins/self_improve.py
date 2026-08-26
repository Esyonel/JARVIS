"""
JARVIS plugin — self-modification: on request, JARVIS can extend its own
source code, including core files (main.py, ui.py, core/, actions/), not
just drop-in plugins.

Letting an LLM edit the code that IS the running application has real blast
radius, so this is wrapped in a hard safety net:

  1. Before touching the target file, its original content is snapshotted in
     memory (or "didn't exist" for a new file) — scoped to that ONE file, so
     this never has to touch, stage, or commit anything else in the repo.
     (An earlier version did `git add -A` + a whole-tree checkpoint commit,
     which silently swept up any unrelated uncommitted work in the repo —
     including this plugin's own file if it had been mid-edit.)
  2. Gemini proposes a TARGETED search/replace edit (old_string -> new_string)
     for an existing file, or full content for a brand new file — never a
     silent full-file rewrite of something already there.
  3. An edit only applies if old_string is found in the file EXACTLY ONCE
     (same rule as a normal precise find/replace) — ambiguous edits are
     rejected rather than guessed at.
  4. Every changed .py file is syntax-checked (py_compile) immediately after.
  5. ANY failure (old_string not found/not unique, syntax error) restores the
     snapshotted file content — JARVIS is never left broken, and no other
     file in the tree is touched.
  6. Never touches secrets/personal data (config/api_keys.json,
     memory/long_term.json, .env, .git/) regardless of what's asked.
  7. Changes only take effect after JARVIS is restarted — this tool never
     restarts the running process itself, and never touches this very file
     (self_improve.py) while it's the one running.
  8. On success, only the ONE touched file is `git add`ed and committed —
     any other dirty files in the working tree are left exactly as they were.
"""

import json
import subprocess
import sys
import time
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


def run(parameters: dict, player=None, session_memory=None, autonomous: bool = False) -> str:
    """autonomous=True is used by the unattended daily evolution run: with no
    human watching, changes are restricted to NEW files under plugins/ so an
    unsupervised bad edit can't touch main.py/ui.py/core and break startup."""
    feature = (parameters.get("feature_request") or "").strip()
    if not feature:
        msg = "Sir, I need a description of what to add or change."
        _log(msg, player)
        return msg

    try:
        plan = _ask_gemini_for_edit(feature)
    except Exception as e:
        msg = f"Sir, I couldn't draft a change for that: {e}"
        _log(msg, player)
        return msg

    if autonomous and (plan.get("mode") != "new_file"
                       or not str(plan.get("file", "")).replace("\\", "/").startswith("plugins/")):
        msg = ("Sir, an unattended run may only add new plugin files, and this change "
               "wanted to touch core code — skipped, nothing was modified.")
        _log(msg, player)
        return msg

    ok, detail = _validate_plan(plan)
    if not ok:
        msg = f"Sir, the drafted change didn't look safe ({detail}), so I skipped it — nothing was touched."
        _log(msg, player)
        return msg

    file_rel = plan["file"].replace("\\", "/").lstrip("/")
    original = _snapshot_before_edit(file_rel)

    try:
        target = _apply_plan(plan)
    except Exception as e:
        _restore_snapshot(file_rel, original)
        msg = f"Sir, applying the change failed ({e}) — reverted, JARVIS is untouched."
        _log(msg, player)
        return msg

    compile_error = _check_syntax(target)
    if compile_error:
        _restore_snapshot(file_rel, original)
        msg = f"Sir, the new code had a syntax error ({compile_error}) — reverted automatically, JARVIS is untouched."
        _log(msg, player)
        return msg

    import_error = _check_imports_available(target)
    if import_error:
        _restore_snapshot(file_rel, original)
        msg = (f"Sir, the new code needs a package that isn't installed ({import_error}) — "
               "reverted automatically rather than leaving a plugin that only reports "
               "'library not found'.")
        _log(msg, player)
        return msg

    plugin_error = _check_plugin_validity(target)
    if plugin_error:
        _restore_snapshot(file_rel, original)
        msg = f"Sir, the new plugin didn't pass validation ({plugin_error}) — reverted automatically, JARVIS is untouched."
        _log(msg, player)
        return msg

    try:
        _git_finalize(feature, file_rel)
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


def _snapshot_before_edit(file_rel: str) -> str | None:
    """Original content of the file about to be touched, or None if it
    doesn't exist yet (new_file mode) — used to restore ONLY this file if
    anything downstream fails, without touching the rest of the tree."""
    target = BASE_DIR / file_rel
    return target.read_text(encoding="utf-8") if target.exists() else None


def _restore_snapshot(file_rel: str, original: str | None) -> None:
    target = BASE_DIR / file_rel
    try:
        if original is None:
            target.unlink(missing_ok=True)
        else:
            target.write_text(original, encoding="utf-8")
    except Exception as e:
        print(f"[SelfImprove] CRITICAL: restoring {file_rel} failed: {e}")


def _git_finalize(feature: str, file_rel: str) -> None:
    """Stages and commits ONLY the touched file — any other dirty files
    elsewhere in the working tree (in-progress human edits, say) are left
    exactly as they were."""
    _git(["add", "--", file_rel])
    status = _git(["status", "--porcelain", "--", file_rel])
    if status.strip():
        _git(["commit", "-m", f"self-improve: {feature[:80]}", "--", file_rel])


# ── Drafting the change ──────────────────────────────────────────────────────

def _ask_gemini_for_edit(feature: str) -> dict:
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

    text = gemini_with_retry(None, prompt)
    text = text.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    return json.loads(text)


def gemini_with_retry(client, prompt: str, model: str = "gemini-flash-latest",
                      attempts: int = 4) -> str:
    """Kept as the shared entry point (daily_evolution imports this), but the
    work now goes through core.ai_text.generate, which retries transient errors
    AND fails over to Groq/Cerebras/OpenRouter when Gemini's daily free quota
    (only ~20 calls) runs out. The `client` argument is ignored — providers are
    resolved from config each call so adding a key takes effect immediately."""
    from core.ai_text import generate
    return generate(prompt)


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


def _check_imports_available(file_rel: str) -> str | None:
    """Rejects generated code that imports a package which isn't installed.

    py_compile and the plugin loader both PASS such a file when the import sits
    inside a try/except in run() — the plugin then loads fine and simply answers
    "library not found" forever. Checking the imports statically catches that
    before it ships. Returns the offending module name, or None if all resolve.
    """
    import ast
    import importlib.util

    try:
        tree = ast.parse((BASE_DIR / file_rel).read_text(encoding="utf-8"))
    except Exception as e:
        return f"parse failed: {e}"

    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            modules.add(node.module.split(".")[0])

    for name in sorted(modules):
        # Local packages resolve by path, not by installation.
        if (BASE_DIR / name).is_dir() or (BASE_DIR / f"{name}.py").exists():
            continue
        try:
            if importlib.util.find_spec(name) is None:
                return name
        except Exception:
            return name
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
