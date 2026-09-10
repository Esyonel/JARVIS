import platform

# psutil is optional; import lazily to avoid import errors on non‑Windows platforms
try:
    import psutil
except Exception:  # pragma: no cover
    psutil = None

PLUGIN = {
    "name": "windows_service_manager",
    "description": "List, start, stop, or restart Windows services using psutil.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "description": "One of: list, start, stop, restart."
            },
            "service_name": {
                "type": "STRING",
                "description": "Name of the Windows service (required for start/stop/restart)."
            }
        },
        "required": ["action"]
    }
}


def _is_windows() -> bool:
    """Return True if the current OS is Windows."""
    return platform.system().lower() == "windows"


def _list_services() -> str:
    """Return a short string with a few services and their statuses.

    The function limits output to the first 10 services to keep the spoken
    response concise. If more detail is needed the user can request a specific
    service name.
    """
    if not psutil:
        return "psutil library is not available."
    try:
        services = list(psutil.win_service_iter())
    except Exception as e:  # pragma: no cover
        return f"Unable to retrieve services: {e}"
    if not services:
        return "No Windows services were found."
    # Sort alphabetically for deterministic output
    services.sort(key=lambda s: s.name())
    lines = []
    for svc in services[:10]:
        try:
            status = svc.status()
        except Exception:  # pragma: no cover
            status = "unknown"
        lines.append(f"{svc.name()}: {status}")
    return "Here are some Windows services: " + ", ".join(lines) + "."


def _perform_action(action: str, service_name: str) -> str:
    """Start, stop or restart a named Windows service.

    Returns a short human‑readable message describing the outcome.
    """
    if not psutil:
        return "psutil library is not available, cannot manage services."
    try:
        svc = psutil.win_service_get(service_name)
    except Exception as e:  # pragma: no cover
        return f"Service '{service_name}' not found: {e}"
    try:
        if action == "start":
            svc.start()
            return f"Service '{service_name}' started successfully."
        elif action == "stop":
            svc.stop()
            return f"Service '{service_name}' stopped successfully."
        elif action == "restart":
            # psutil does not provide a direct restart, emulate it
            svc.stop()
            svc.wait()  # wait for stop to complete
            svc.start()
            return f"Service '{service_name}' restarted successfully."
        else:
            return f"Unsupported action '{action}'."
    except Exception as e:  # pragma: no cover
        return f"Failed to {action} service '{service_name}': {e}"


def run(parameters: dict, player=None, session_memory=None) -> str:
    """Entry point for the plugin.

    Parameters
    ----------
    parameters: dict
        Must contain an ``action`` key (list, start, stop, restart). If the
        action is not ``list`` a ``service_name`` key is required.
    player, session_memory: optional, ignored by this plugin.

    Returns
    -------
    str
        A short plain‑text message suitable for spoken output.
    """
    if not _is_windows():
        return "Windows service management is only available on Windows platforms."
    action = parameters.get("action", "").lower()
    if not action:
        return "No action provided. Please specify one of: list, start, stop, restart."
    if action == "list":
        return _list_services()
    service_name = parameters.get("service_name", "")
    if not service_name:
        return "Service name is required for start, stop, or restart actions."
    return _perform_action(action, service_name)
