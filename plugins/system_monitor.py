'''System Monitor Plugin

Collects CPU, RAM, and network usage periodically using ``psutil`` and
creates an instantaneous line‑chart PNG saved on the user's Desktop.
The chart is refreshed every few seconds while the background thread is
alive.

The plugin follows the standard JARVIS plugin contract:

* ``PLUGIN`` dictionary describes the plugin.
* ``run`` function returns a short spoken response and never raises.
''' 

import threading
import time
from pathlib import Path
from typing import List

import numpy as np
import psutil
from PIL import Image, ImageDraw, ImageFont

# ---------------------------------------------------------------------------
# Plugin metadata – must be present exactly as JARVIS expects.
# ---------------------------------------------------------------------------
PLUGIN = {
    "name": "system_monitor",
    "description": "Periodically records CPU, RAM and network usage and saves a live graph PNG on the Desktop.",
    "parameters": {
        "type": "OBJECT",
        "properties": {},
        "required": []
    }
}

# ---------------------------------------------------------------------------
# Internal state – a daemon thread that keeps running after the plugin is
# invoked.  The thread is created only once per interpreter session.
# ---------------------------------------------------------------------------
_monitor_thread: threading.Thread | None = None
_stop_event = threading.Event()

# Configuration constants – easy to tweak if needed.
_INTERVAL_SECONDS = 2               # sampling interval
_MAX_SAMPLES = 60                    # how many points to keep for the chart
_IMG_WIDTH = 500
_IMG_HEIGHT = 250
_IMG_PATH = Path.home() / "Desktop" / "system_monitor.png"

# ---------------------------------------------------------------------------
# Helper functions for chart rendering.
# ---------------------------------------------------------------------------
def _scale_to_height(values: List[float], height: int) -> List[int]:
    """Scale a list of float values (0‑100) to pixel y‑coordinates.
    The y‑origin in Pillow is at the top, so higher values map to lower
    pixel numbers.
    """
    if not values:
        return []
    arr = np.array(values, dtype=float)
    # Clamp to 0‑100 to avoid surprises.
    arr = np.clip(arr, 0, 100)
    # Invert because Pillow's y‑axis grows downwards.
    scaled = height - (arr / 100.0 * height).astype(int)
    return scaled.tolist()

def _draw_chart(cpu: List[float], ram: List[float], net: List[float]):
    """Draw the three series on a PNG and write it to ``_IMG_PATH``.
    ``cpu``, ``ram`` and ``net`` are lists of the same length containing
    percentages (0‑100).
    """
    img = Image.new("RGB", (_IMG_WIDTH, _IMG_HEIGHT), "white")
    draw = ImageDraw.Draw(img)

    # Draw simple axes.
    margin = 40
    plot_w = _IMG_WIDTH - 2 * margin
    plot_h = _IMG_HEIGHT - 2 * margin
    left, top = margin, margin
    right, bottom = left + plot_w, top + plot_h
    draw.rectangle([left, top, right, bottom], outline="gray")

    # Prepare X coordinates (evenly spaced).
    n = len(cpu)
    if n == 0:
        img.save(_IMG_PATH)
        return
    x_coords = np.linspace(left, right, n).astype(int).tolist()

    # Scale Y values.
    cpu_y = _scale_to_height(cpu, plot_h)
    ram_y = _scale_to_height(ram, plot_h)
    net_y = _scale_to_height(net, plot_h)

    # Offset Y by top margin.
    cpu_y = [y + top for y in cpu_y]
    ram_y = [y + top for y in ram_y]
    net_y = [y + top for y in net_y]

    # Draw lines.
    draw.line(list(zip(x_coords, cpu_y)), fill="red", width=2)
    draw.line(list(zip(x_coords, ram_y)), fill="green", width=2)
    draw.line(list(zip(x_coords, net_y)), fill="blue", width=2)

    # Legend (tiny text – fallback to default font if unavailable).
    try:
        font = ImageFont.truetype("arial.ttf", 12)
    except Exception:
        font = ImageFont.load_default()
    legend_y = top - 20
    draw.text((left, legend_y), "CPU", fill="red", font=font)
    draw.text((left + 50, legend_y), "RAM", fill="green", font=font)
    draw.text((left + 100, legend_y), "Net", fill="blue", font=font)

    img.save(_IMG_PATH)

# ---------------------------------------------------------------------------
# Background monitoring loop.
# ---------------------------------------------------------------------------
def _monitor_loop():
    cpu_samples: List[float] = []
    ram_samples: List[float] = []
    net_samples: List[float] = []
    prev_net_bytes = psutil.net_io_counters().bytes_sent + psutil.net_io_counters().bytes_recv

    while not _stop_event.is_set():
        try:
            cpu = psutil.cpu_percent(interval=None)
            ram = psutil.virtual_memory().percent
            cur_net_bytes = psutil.net_io_counters().bytes_sent + psutil.net_io_counters().bytes_recv
            net_rate = (cur_net_bytes - prev_net_bytes) / _INTERVAL_SECONDS / (1024 * 1024) * 100  # normalized to % scale
            prev_net_bytes = cur_net_bytes

            # Keep values within 0‑100 for chart consistency.
            net_rate = max(0.0, min(100.0, net_rate))

            cpu_samples.append(cpu)
            ram_samples.append(ram)
            net_samples.append(net_rate)

            # Trim old data.
            if len(cpu_samples) > _MAX_SAMPLES:
                cpu_samples = cpu_samples[-_MAX_SAMPLES:]
                ram_samples = ram_samples[-_MAX_SAMPLES:]
                net_samples = net_samples[-_MAX_SAMPLES:]

            _draw_chart(cpu_samples, ram_samples, net_samples)
        except Exception as exc:
            # Logging is optional – we just swallow to keep the thread alive.
            print(f"[system_monitor] monitoring error: {exc}")
        finally:
            time.sleep(_INTERVAL_SECONDS)

# ---------------------------------------------------------------------------
# Public entry point – invoked by JARVIS.
# ---------------------------------------------------------------------------
def run(parameters: dict, player=None, session_memory=None) -> str:
    """Start the background system‑monitoring thread.

    The function is safe to call multiple times; subsequent calls will
    simply inform the user that the monitor is already running.
    """
    global _monitor_thread
    try:
        if _monitor_thread and _monitor_thread.is_alive():
            return "System monitor is already running; the live graph is being updated on your Desktop."

        # Reset stop flag and launch daemon thread.
        _stop_event.clear()
        _monitor_thread = threading.Thread(target=_monitor_loop, daemon=True)
        _monitor_thread.start()
        return "System monitor started. A live performance graph is being saved to your Desktop."
    except Exception as e:
        return f"Failed to start system monitor: {e}"
