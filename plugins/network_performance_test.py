import subprocess
import re
from typing import List, Dict

# Plugin metadata required by JARVIS
PLUGIN = {
    "name": "network_performance_test",
    "description": "Runs Windows ping on a list of domains/IPs and reports average latency, packet loss and jitter.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "targets": {
                "type": "ARRAY",
                "items": {"type": "STRING"},
                "description": "List of domain names or IP addresses to test."
            },
            "count": {
                "type": "INTEGER",
                "default": 4,
                "description": "Number of echo requests per target."
            }
        },
        "required": ["targets"]
    }
}

def _run_ping(target: str, count: int) -> Dict[str, float]:
    """Execute Windows ping and extract latency, loss and jitter.

    Returns a dict with keys: avg_latency, packet_loss, jitter. All values are in ms
    (packet_loss is a percentage).
    """
    try:
        # -n count : number of echo requests
        # -w 1000 : timeout per reply in ms
        result = subprocess.run(
            ["ping", "-n", str(count), "-w", "1000", target],
            capture_output=True,
            text=True,
            shell=False,
            timeout=15,
        )
        output = result.stdout
    except Exception as e:
        return {"error": f"Failed to run ping on {target}: {e}"}

    # Extract per‑reply times (e.g., "time=15ms")
    time_matches = re.findall(r"time[=<]\s*(\d+)ms", output)
    times = [int(t) for t in time_matches]

    # Extract packet loss from summary line
    loss_match = re.search(r"Lost = (\d+) \((\d+)% loss\)", output)
    if loss_match:
        lost = int(loss_match.group(1))
        loss_percent = int(loss_match.group(2))
    else:
        # fallback if pattern differs
        loss_percent = 100.0 if not times else 0.0
        lost = count - len(times)

    # Compute average latency
    avg_latency = sum(times) / len(times) if times else 0.0

    # Compute jitter as average absolute difference between successive pings
    jitter = 0.0
    if len(times) > 1:
        diffs = [abs(times[i] - times[i - 1]) for i in range(1, len(times))]
        jitter = sum(diffs) / len(diffs)

    return {
        "avg_latency": avg_latency,
        "packet_loss": loss_percent,
        "jitter": jitter,
    }

def run(parameters: dict, player=None, session_memory=None) -> str:
    """Entry point for the plugin.

    Expected parameters:
        - targets (list of strings): domains or IPs to test.
        - count (int, optional): number of ping packets per target (default 4).
    Returns a short spoken summary.
    """
    try:
        targets: List[str] = parameters.get("targets", [])
        if not isinstance(targets, list) or not targets:
            return "Please provide at least one domain or IP address to test."
        count: int = int(parameters.get("count", 4))
        reports = []
        for tgt in targets:
            stats = _run_ping(tgt, count)
            if "error" in stats:
                reports.append(stats["error"])
                continue
            avg = round(stats["avg_latency"], 1)
            loss = round(stats["packet_loss"], 1)
            jitter = round(stats["jitter"], 1)
            reports.append(
                f"Ping test for {tgt}: average latency {avg} ms, packet loss {loss} percent, jitter {jitter} ms."
            )
        return " ".join(reports)
    except Exception as exc:
        return f"An error occurred while performing the network test: {exc}"
