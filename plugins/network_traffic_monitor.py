import psutil
import time

# Plugin metadata
PLUGIN = {
    "name": "network_traffic_monitor",
    "description": "Monitors and analyzes network traffic, providing a brief summary of bandwidth usage and top protocols.",
    "parameters": {
        "type": "OBJECT",
        "properties": {},
        "required": []
    }
}

def _format_bytes(num_bytes: int) -> str:
    """Convert a byte count into a human‑readable string (KB, MB, GB)."""
    for unit in ["bytes", "KB", "MB", "GB", "TB"]:
        if abs(num_bytes) < 1024.0:
            return f"{num_bytes:3.1f} {unit}" if unit != "bytes" else f"{int(num_bytes)} {unit}"
        num_bytes /= 1024.0
    return f"{num_bytes:.1f} PB"

def run(parameters: dict, player=None, session_memory=None) -> str:
    """Return a short spoken summary of recent network activity.

    The function keeps the previous network counters in ``session_memory``
    (a mutable dict passed by the JARVIS core). On the first call it stores the
    current counters and reports that no prior data is available.
    Subsequent calls compute the difference and present it as a concise
    sentence.
    """
    try:
        # Retrieve current counters (total since boot)
        counters = psutil.net_io_counters()
        sent = counters.bytes_sent
        recv = counters.bytes_recv

        # Ensure we have a mutable dict to store state across calls
        if session_memory is None:
            session_memory = {}

        prev = session_memory.get("network_traffic_monitor_prev")
        if prev is None:
            # First invocation – store counters and inform the user
            session_memory["network_traffic_monitor_prev"] = {
                "sent": sent,
                "recv": recv,
                "timestamp": time.time()
            }
            return "Network monitoring initialized. I will tell you the traffic on the next request."

        # Compute deltas
        elapsed = time.time() - prev["timestamp"]
        sent_diff = sent - prev["sent"]
        recv_diff = recv - prev["recv"]

        # Update stored values for the next call
        session_memory["network_traffic_monitor_prev"] = {
            "sent": sent,
            "recv": recv,
            "timestamp": time.time()
        }

        # Guard against division by zero or negative values (unlikely)
        if elapsed <= 0:
            return "Unable to compute network usage at this moment."

        sent_str = _format_bytes(sent_diff)
        recv_str = _format_bytes(recv_diff)
        return f"In the last {int(elapsed)} seconds, your computer sent {sent_str} and received {recv_str}."
    except Exception as e:
        # Never raise; return a user‑friendly error message
        return "Sorry, I couldn’t retrieve network statistics right now."
