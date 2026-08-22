"""
Provider-failover text generation for JARVIS's non-voice AI work.

Gemini's free tier allows only ~20 generate_content calls per day, which is
easily exhausted by plugins, the daily evolution run, and agent work — after
which every AI-backed feature dies with a 429. This layer tries Gemini first,
then transparently falls back to other providers that are OpenAI-compatible
and have far more generous free tiers.

Only providers with a key in config/api_keys.json are attempted; the rest are
skipped silently, so adding a key is the only step needed to enable one.

Keys are read from config/api_keys.json:
    "gemini_api_key"      (already present — primary)
    "groq_api_key"        free, very generous: https://console.groq.com/keys
    "cerebras_api_key"    free tier:           https://cloud.cerebras.ai
    "openrouter_api_key"  free models:         https://openrouter.ai/keys

NOTE: this is for TEXT generation only. The live voice session is a
Gemini-specific realtime API with no equivalent elsewhere, so it cannot fail
over — a voice outage still needs Gemini quota.
"""

import json
import time
from pathlib import Path

import requests

BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_PATH = BASE_DIR / "config" / "api_keys.json"

_TIMEOUT = 60

# Tried in order. Each entry: (config key, base url, default model).
# Model ids verified against each provider's live /models endpoint — these
# providers retire model names regularly, so a 404 here means the id was
# dropped upstream; re-check /models rather than assuming the key is bad.
_OPENAI_COMPATIBLE = [
    ("groq_api_key",       "https://api.groq.com/openai/v1", "openai/gpt-oss-120b"),
    ("cerebras_api_key",   "https://api.cerebras.ai/v1",     "gpt-oss-120b"),
    ("openrouter_api_key", "https://openrouter.ai/api/v1",   "meta-llama/llama-3.3-70b-instruct:free"),
]


def _config() -> dict:
    try:
        return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _is_transient(error: Exception) -> bool:
    """Server hiccup — worth retrying the SAME provider."""
    return any(k in str(error) for k in ("503", "UNAVAILABLE", "500", "502", "504"))


def _is_exhausted(error: Exception) -> bool:
    """Quota/rate limit — retrying this provider is pointless, move to the next."""
    return any(k in str(error) for k in ("429", "RESOURCE_EXHAUSTED", "quota", "insufficient_quota"))


def generate(prompt: str, model: str | None = None) -> str:
    """Returns generated text, trying each configured provider in turn.

    Raises RuntimeError only if every configured provider failed — the message
    lists what was tried and why each one failed, so the cause is never guessed at.
    """
    cfg = _config()
    failures: list[str] = []

    # Gemini is tried LAST on purpose. Its free tier is only ~20 calls/day and
    # the live voice session can ONLY run on Gemini — no other provider offers
    # that realtime audio API. Spending that quota on text work would silently
    # cost the voice assistant its voice, so text falls to the other providers
    # first and only reaches Gemini if every one of them is unavailable.
    from core.api_usage import record

    for key_name, base_url, default_model in _OPENAI_COMPATIBLE:
        key = cfg.get(key_name)
        if not key:
            continue
        provider = key_name.replace("_api_key", "")
        try:
            text = _openai_compatible(key, base_url, default_model, prompt)
            record(provider)
            return text
        except Exception as e:
            failures.append(f"{provider}: {str(e)[:120]}")

    from core.gemini_keys import call_with_rotation, all_keys
    if all_keys():
        try:
            return call_with_rotation(_gemini, prompt, model or "gemini-flash-latest")
        except Exception as e:
            failures.append(f"gemini: {str(e)[:120]}")

    if not failures:
        raise RuntimeError("No AI provider is configured — add gemini_api_key or groq_api_key.")
    raise RuntimeError("All AI providers failed — " + " | ".join(failures))


def _gemini(key: str, prompt: str, model: str, attempts: int = 3) -> str:
    from google import genai

    client = genai.Client(api_key=key)
    for attempt in range(attempts):
        try:
            resp = client.models.generate_content(model=model, contents=prompt)
            text = (resp.text or "").strip()
            if not text:
                raise RuntimeError("empty response")
            return text
        except Exception as e:
            if _is_exhausted(e):
                raise  # quota gone for the day — let the caller fall through
            if not _is_transient(e) or attempt == attempts - 1:
                raise
            time.sleep(2 ** attempt)
    raise RuntimeError("unreachable")


def _openai_compatible(key: str, base_url: str, model: str, prompt: str,
                       attempts: int = 3) -> str:
    for attempt in range(attempts):
        try:
            resp = requests.post(
                f"{base_url}/chat/completions",
                headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                json={"model": model, "messages": [{"role": "user", "content": prompt}]},
                timeout=_TIMEOUT,
            )
            if resp.status_code == 429:
                raise RuntimeError(f"429 rate limited: {resp.text[:150]}")
            resp.raise_for_status()
            text = (resp.json()["choices"][0]["message"]["content"] or "").strip()
            if not text:
                raise RuntimeError("empty response")
            return text
        except Exception as e:
            if _is_exhausted(e):
                raise
            if not _is_transient(e) or attempt == attempts - 1:
                raise
            time.sleep(2 ** attempt)
    raise RuntimeError("unreachable")


def available_providers() -> list[str]:
    """Which providers currently have a key configured (for diagnostics)."""
    cfg = _config()
    names = []
    if cfg.get("gemini_api_key"):
        names.append("gemini")
    for key_name, _url, _model in _OPENAI_COMPATIBLE:
        if cfg.get(key_name):
            names.append(key_name.replace("_api_key", ""))
    return names
