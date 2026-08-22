"""
JARVIS plugin — the CIO orchestrator entry point.

Hands a multi-part request to core.agents, which decomposes it, routes each
piece to the specialist agent that owns the right tool, runs those agents in
parallel, and merges what they return into one spoken answer.

Use this only for requests that genuinely span several capabilities. A request
one tool already answers should call that tool directly — routing it through
the orchestrator just adds two model calls and latency for the same result.
"""

from core.agents import AGENTS, run_goal

PLUGIN = {
    "name": "orchestrator",
    "description": (
        "Handles a COMPOUND request that needs several different capabilities at "
        "once by splitting it across specialist agents (system, office/Excel, web, "
        "code, memory) and merging their results. Use when one request contains "
        "multiple distinct jobs — e.g. 'borsayı kontrol et, haberleri özetle ve "
        "diskimin doluluğunu söyle', 'şu Excel'i oku ve piyasa verisiyle karşılaştır', "
        "'sistem durumunu kontrol et ve takvimime bak'. Do NOT use it when a single "
        "tool already answers the request — call that tool directly instead."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "goal": {
                "type": "STRING",
                "description": "The user's full compound request, verbatim, in their own language.",
            },
        },
        "required": ["goal"],
    },
}


def run(parameters: dict, player=None, session_memory=None) -> str:
    goal = (parameters.get("goal") or "").strip()
    if not goal:
        msg = "Efendim, ajanlara dağıtmam için bir görev söylemelisiniz."
        _log(msg, player)
        return msg

    registry = _get_registry()
    if registry is None:
        msg = "Efendim, ajan sistemi eklenti kaydına ulaşamadı."
        _log(msg, player)
        return msg

    result = run_goal(goal, registry, player=player)
    _log(result, player)
    return result[:3000]


def _get_registry():
    """Reuse the live process's plugin registry when JARVIS is running; fall
    back to a fresh scan so the orchestrator is also testable standalone."""
    try:
        import main
        registry = getattr(main, "_ACTIVE_PLUGIN_REGISTRY", None)
        if registry is not None:
            return registry
    except Exception:
        pass

    try:
        from pathlib import Path

        from core.plugin_loader import discover_plugins
        base = Path(__file__).resolve().parent.parent
        return discover_plugins(base / "plugins", core_tool_names=set(), logger=lambda _m: None)
    except Exception:
        return None


def agent_roster() -> str:
    """Human-readable listing of the agent hierarchy (used by tests/diagnostics)."""
    lines = ["CIO (orchestrator) — görevi böler, yönlendirir, sonuçları birleştirir",
             "CFO — piyasa/para içeren adımları denetler: sadece veri, tavsiye yok"]
    lines += [f"  └ {spec['title']}: {spec['role']}" for spec in AGENTS.values()]
    return "\n".join(lines)


def _log(message: str, player=None) -> None:
    print(f"[Orchestrator] {message[:300]}")
    if player:
        try:
            player.write_log(f"JARVIS: {message}")
        except Exception:
            pass
