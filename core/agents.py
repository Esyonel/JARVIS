"""
Multi-agent layer for JARVIS: an orchestrator that decomposes a request,
routes each piece to a specialist agent, runs them, and merges the results.

Design note — why agents don't each get their own LLM call:
    A textbook hierarchy (orchestrator -> supervisor -> N agents, each an LLM
    conversation) costs 5-10 model calls per request. On free provider tiers
    that is a handful of requests per day, and most of those calls would only
    be re-deciding something already decided. So the split here is:

        1 call   decompose the goal into steps, each bound to an agent + tool
        0 calls  agents execute their steps deterministically via plugins,
                 in parallel where the steps don't depend on each other
        1 call   merge the collected results into one spoken answer

    The agents are still real — each owns a role, a bounded toolset, and runs
    independently — but thinking happens where it changes an outcome.

Hierarchy:
    CIO  (Chief Information Officer) — the orchestrator: owns intent, planning
         and routing across every information-producing agent.
    CFO  (Chief Financial Officer)   — reviews any step touching money/markets
         and is the reason such steps report figures only, never advice.
    Specialists — system, office, web, code, memory (see AGENTS below).
"""

import concurrent.futures
import json
from dataclasses import dataclass, field

from core.ai_text import generate

# Each specialist owns a bounded set of plugins. A step may only call a plugin
# its assigned agent owns — that boundary is what keeps a mis-planned step from
# reaching an unrelated capability.
AGENTS: dict[str, dict] = {
    "system": {
        "title": "System & Automation Agent",
        "role": "Yerel makine işlemleri: donanım durumu, ağ, loglar, proje başlatma, saat.",
        # NOTE: these are PLUGIN['name'] values, not file names — they differ
        # (scan_local_network lives in network_scanner.py). Using a file name
        # here silently drops the tool, so unknown_tools() checks them at runtime.
        "plugins": ["project_launcher", "log_watcher", "disk_usage", "scan_local_network",
                    "get_current_time_date", "self_evolution"],
    },
    "office": {
        "title": "Office & Data Agent",
        "role": "Excel/CSV dosyaları: okuma, yazma, birleştirme, formül yardımı.",
        "plugins": ["excel_reader", "excel_writer", "excel_formula_helper", "excel_merge_cleaner"],
    },
    "web": {
        "title": "Web & Search Agent",
        "role": "Dış dünya verisi: haberler, hava durumu, piyasa/kripto verileri, WhatsApp arşivi.",
        "plugins": ["daily_briefing", "market_data", "whatsapp_reader"],
    },
    "code": {
        "title": "Code & Analysis Agent",
        "role": "Kod tarafı: git değişiklikleri, JARVIS'in kendi kodunu geliştirmesi.",
        "plugins": ["git_summary", "self_improve"],
    },
    "memory": {
        "title": "Memory & Context Agent",
        "role": "Kalıcı bağlam: takvim, randevular, hatırlatmalar.",
        "plugins": ["calendar_manager"],
    },
}

# Steps whose results the CFO reviews. Market data must come back as figures
# and their textbook meaning — never a buy/sell call or a price prediction.
_CFO_PLUGINS = {"market_data"}

MAX_STEPS = 5


@dataclass
class Step:
    agent: str
    plugin: str
    parameters: dict = field(default_factory=dict)
    why: str = ""
    result: str = ""
    ok: bool = False


def unknown_tools(available: set[str]) -> dict[str, list[str]]:
    """Tools listed in AGENTS that no loaded plugin actually registers.

    A typo or a file-name/plugin-name mismatch here is invisible at runtime —
    the step just never gets planned and the agent looks like it has no tools —
    so this is surfaced explicitly rather than left to be noticed by accident.
    """
    missing: dict[str, list[str]] = {}
    for name, spec in AGENTS.items():
        gone = [p for p in spec["plugins"] if p not in available]
        if gone:
            missing[name] = gone
    return missing


def plan(goal: str, available: set[str]) -> list[Step]:
    for agent_name, gone in unknown_tools(available).items():
        print(f"[Agents] '{agent_name}' ajanında kayıtlı olmayan araç(lar): {', '.join(gone)}")

    """CIO: turn a goal into ordered steps, each bound to one agent + plugin."""
    roster = "\n".join(
        f"- {name} ({spec['title']}): {spec['role']}\n"
        f"  araçlar: {', '.join(p for p in spec['plugins'] if p in available)}"
        for name, spec in AGENTS.items()
        if any(p in available for p in spec["plugins"])
    )

    prompt = (
        "You are the CIO of a Turkish voice assistant. Break the user's request into "
        "the fewest steps that actually answer it, and assign each step to one agent "
        "and one of THAT agent's tools.\n\n"
        f"Agents and their tools:\n{roster}\n\n"
        f"User request: {goal}\n\n"
        f"Reply with ONLY a JSON array (no markdown), at most {MAX_STEPS} items:\n"
        '[{"agent": "web", "plugin": "market_data", "parameters": {"category": "bist"}, '
        '"why": "kısa gerekçe"}]\n\n'
        "Rules: a step's plugin MUST belong to its agent. Use the exact plugin names "
        "listed. If one tool alone answers the request, return exactly one step. "
        "If nothing fits, return []."
    )

    raw = generate(prompt).strip()
    raw = raw.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    parsed = json.loads(raw)

    steps: list[Step] = []
    for item in parsed[:MAX_STEPS]:
        agent = str(item.get("agent", "")).strip()
        plugin = str(item.get("plugin", "")).strip()
        if agent not in AGENTS or plugin not in AGENTS[agent]["plugins"]:
            continue  # planner strayed outside the agent's boundary — drop the step
        if plugin not in available:
            continue
        params = item.get("parameters") or {}
        steps.append(Step(agent=agent, plugin=plugin,
                          parameters=params if isinstance(params, dict) else {},
                          why=str(item.get("why", ""))[:200]))
    return steps


def execute(steps: list[Step], registry, player=None) -> list[Step]:
    """Run every step through its agent's plugin, in parallel — one failing
    step records its error and never stops the others."""
    def _one(step: Step) -> Step:
        try:
            step.result = str(registry.run(step.plugin, step.parameters, player=player))
            step.ok = True
        except Exception as e:
            step.result = f"hata: {e}"
            step.ok = False
        return step

    if not steps:
        return steps
    with concurrent.futures.ThreadPoolExecutor(max_workers=min(len(steps), 5)) as pool:
        return list(pool.map(_one, steps))


def merge(goal: str, steps: list[Step]) -> str:
    """Combine the agents' outputs into one spoken Turkish answer."""
    transcript = "\n\n".join(
        f"[{AGENTS[s.agent]['title']} / {s.plugin}]\n{s.result[:1200]}"
        for s in steps
    )

    cfo_clause = ""
    if any(s.plugin in _CFO_PLUGINS for s in steps):
        cfo_clause = (
            "\n\nCFO KURALI: Piyasa verisi içeren adımlarda yalnızca rakamları ve "
            "bunların ders kitabı anlamını aktar. Asla al/sat tavsiyesi verme, "
            "asla fiyatın yükseleceğini/düşeceğini söyleme."
        )

    prompt = (
        "You are JARVIS answering your owner in Turkish, out loud. Below are the raw "
        "outputs your specialist agents produced for the request. Merge them into one "
        "natural spoken answer.\n\n"
        f"İstek: {goal}\n\n"
        f"Ajan çıktıları:\n{transcript}\n\n"
        "Kısa ve doğrudan ol. Sadece çıktılarda geçen bilgiyi kullan, hiçbir şey uydurma. "
        "Bir adım hata verdiyse bunu dürüstçe söyle." + cfo_clause
    )
    return generate(prompt).strip()


def run_goal(goal: str, registry, player=None) -> str:
    """Full CIO cycle: plan -> agents execute in parallel -> merge."""
    available = {name for name in registry._plugins}

    try:
        steps = plan(goal, available)
    except Exception as e:
        return f"Efendim, görevi ajanlara bölemedim: {e}"

    if not steps:
        return "Efendim, bu istek için uygun bir ajan/araç bulamadım."

    steps = execute(steps, registry, player=player)

    try:
        return merge(goal, steps)
    except Exception as e:
        # Merging is a nicety — the agents' own results are the actual answer,
        # so a failed merge must not throw them away.
        lines = [f"{AGENTS[s.agent]['title']}: {s.result[:400]}" for s in steps]
        return f"(Birleştirme başarısız: {e})\n" + "\n".join(lines)
