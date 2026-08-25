PLUGIN = {
    "name": "download_monitor",
    "description": "Checks the system's Downloads folder and reports recent files.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "path": {
                "type": "string",
                "description": "Custom path to monitor. Defaults to the user's Downloads folder."
            },
            "recent_minutes": {
                "type": "integer",
                "description": "Time window in minutes to look back for recent downloads. Default is 5 minutes."
            }
        },
        "required": []
    }
}

def run(parameters: dict, player=None, session_memory=None) -> str:
    """Check the Downloads directory for recent files.

    Returns a short spoken‑language string describing recent downloads or an error.
    """
    try:
        import os
        import time
        # Resolve the path to monitor
        path = parameters.get("path")
        if not path:
            path = os.path.expanduser(os.path.join("~", "Downloads"))
        # Resolve the time window
        recent_minutes = parameters.get("recent_minutes", 5)
        try:
            recent_minutes = int(recent_minutes)
        except Exception:
            recent_minutes = 5
        cutoff = time.time() - recent_minutes * 60
        # Gather recent files
        recent_files = []
        if os.path.isdir(path):
            for entry in os.scandir(path):
                if entry.is_file():
                    try:
                        if entry.stat().st_mtime >= cutoff:
                            recent_files.append(entry.name)
                    except Exception:
                        continue
        else:
            return f"The path {path} does not exist or is not a directory."
        if not recent_files:
            return "There are no recent downloads."
        # Limit output length for speaking
        displayed = recent_files[:5]
        more = len(recent_files) - len(displayed)
        result = f"Recent downloads: {', '.join(displayed)}"
        if more > 0:
            result += f", and {more} more."
        return result
    except Exception as exc:
        return f"Error checking downloads: {exc}"