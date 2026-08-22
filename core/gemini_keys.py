"""
Rotating pool of Gemini API keys.

The live voice session can ONLY run on Gemini — no other provider offers that
realtime audio API — and each free-tier key allows only a small number of
calls per day. One key therefore caps how long JARVIS can talk each day, and
when it runs out the session simply stops connecting.

A pool fixes that: keys are tried in order, and a key that reports quota
exhaustion is marked spent for the rest of the day so later calls skip
straight to the next one instead of re-hitting a dead key every time. The
marks are kept in memory only — restarting JARVIS retries every key, which is
correct, since quotas reset on Google's clock, not ours.

Config (config/api_keys.json) accepts either form:
    "gemini_api_key":  "AIza...single"
    "gemini_api_keys": ["AIza...first", "AIza...second", ...]
Both may be present; the single key is used first, then the list.
"""

import json
import threading
from datetime import date
from pathlib import Path

CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "api_keys.json"

_lock = threading.Lock()
_spent: dict[str, date] = {}   # key -> date it was found exhausted


def _config() -> dict:
    try:
        return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def all_keys() -> list[str]:
    """Every configured Gemini key, in preference order, de-duplicated."""
    cfg = _config()
    keys: list[str] = []

    single = cfg.get("gemini_api_key")
    if isinstance(single, str) and single.strip():
        keys.append(single.strip())

    listed = cfg.get("gemini_api_keys")
    if isinstance(listed, list):
        keys += [k.strip() for k in listed if isinstance(k, str) and k.strip()]

    seen, unique = set(), []
    for k in keys:
        if k not in seen:
            seen.add(k)
            unique.append(k)
    return unique


def is_exhausted(error: Exception | str) -> bool:
    text = str(error)
    return any(m in text for m in ("429", "RESOURCE_EXHAUSTED", "quota"))


def mark_exhausted(key: str) -> None:
    """Remember this key is spent for today so it gets skipped from now on."""
    with _lock:
        _spent[key] = date.today()


def available_keys() -> list[str]:
    """Configured keys minus the ones already found exhausted today."""
    today = date.today()
    with _lock:
        spent_today = {k for k, when in _spent.items() if when == today}
    fresh = [k for k in all_keys() if k not in spent_today]
    # Every key spent — hand back the full list anyway so the caller surfaces a
    # real quota error from the API instead of a confusing "no keys" message.
    return fresh or all_keys()


def status() -> str:
    total = len(all_keys())
    fresh = len([k for k in all_keys() if k in available_keys()])
    if total == 0:
        return "Yapılandırılmış Gemini anahtarı yok."
    return f"{total} Gemini anahtarı yapılandırılmış, {fresh} tanesi bugün hâlâ kullanılabilir."


def call_with_rotation(fn, *args, **kwargs):
    """Run fn(key, *args) against each available key until one succeeds.

    A quota error advances to the next key; any other error is raised straight
    away, because retrying a bad request on four keys just burns four keys.
    """
    keys = available_keys()
    if not keys:
        raise RuntimeError("No Gemini API key configured.")

    last_error: Exception | None = None
    for key in keys:
        try:
            return fn(key, *args, **kwargs)
        except Exception as e:
            if not is_exhausted(e):
                raise
            mark_exhausted(key)
            last_error = e
            print(f"[GeminiKeys] Bir anahtarın kotası doldu, sıradakine geçiliyor "
                  f"({keys.index(key) + 1}/{len(keys)}).")
    raise last_error or RuntimeError("All Gemini keys exhausted.")
