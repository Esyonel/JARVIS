"""Windows Update Tracker Plugin

Detects pending Windows updates and reports version, release date, and severity.
"""

import subprocess
import json
from datetime import datetime

PLUGIN = {
    "name": "windows_update_tracker",
    "description": "Detects pending Windows updates and reports version, date, and severity to the user.",
    "parameters": {
        "type": "OBJECT",
        "properties": {},
        "required": []
    }
}


def _run_powershell(command: str) -> str:
    """Execute a PowerShell command and return its stdout.
    Returns an empty string on failure.
    """
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command", command],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            return ""
        return result.stdout.strip()
    except Exception:
        return ""


def run(parameters: dict, player=None, session_memory=None) -> str:
    """Check for pending Windows updates.

    Returns a short spoken string summarising the pending updates.
    """
    # PowerShell script to fetch pending updates as JSON
    ps_script = (
        "$searcher = New-Object -ComObject Microsoft.Update.Searcher; "
        "$updates = $searcher.Search('IsInstalled=0').Updates; "
        "$list = @(); foreach ($u in $updates) { "
        "    $list += [pscustomobject]@{ "
        "        Title = $u.Title; "
        "        KB = ($u.KBArticleIDs -join ','); "
        "        Date = $u.LastDeploymentChangeTime; "
        "        Severity = $u.MsrcSeverity; "
        "    }; "
        "}; "
        "$list | ConvertTo-Json -Compress"
    )

    output = _run_powershell(ps_script)
    if not output:
        return "I couldn't retrieve Windows update information at this time."

    try:
        updates = json.loads(output)
        # PowerShell may return a dict when there is a single update
        if isinstance(updates, dict):
            updates = [updates]
    except Exception:
        return "I received unexpected data while checking for Windows updates."

    if not updates:
        return "There are no pending Windows updates right now."

    # Build a concise summary (limit to first 3 updates for brevity)
    summary_parts = []
    for idx, upd in enumerate(updates[:3], start=1):
        title = upd.get("Title", "Unknown update")
        kb = upd.get("KB", "N/A")
        date_raw = upd.get("Date")
        try:
            # Example format: 2024-04-15T12:34:56Z
            date_obj = datetime.fromisoformat(date_raw.rstrip('Z'))
            date_str = date_obj.strftime("%Y-%m-%d")
        except Exception:
            date_str = date_raw or "unknown date"
        severity = upd.get("Severity", "Unspecified")
        part = f"{idx}. {title} (KB {kb}) released on {date_str}, severity {severity}"
        summary_parts.append(part)

    if len(updates) > 3:
        summary = f"You have {len(updates)} pending Windows updates. " + ", ".join(summary_parts) + ", and more."
    else:
        summary = f"You have {len(updates)} pending Windows update" + ("s" if len(updates) > 1 else "") + ": " + ", ".join(summary_parts) + "."

    return summary