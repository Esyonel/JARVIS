import os
import json
import requests

# ---------------------------------------------------------------------------
# Plugin definition
# ---------------------------------------------------------------------------
PLUGIN = {
    "name": "codebase_intelligence",
    "description": "Query the DeusData Codebase‑Memory‑MCP server for code intelligence. "
                   "Supports sub‑millisecond lookups across 158 languages and returns a concise answer.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "query": {
                "type": "string",
                "description": "The natural‑language question or code search query."
            },
            "codebase_id": {
                "type": "string",
                "description": "Identifier of the indexed codebase on the DeusData server."
            }
        },
        "required": ["query", "codebase_id"]
    }
}

# ---------------------------------------------------------------------------
# Helper: obtain the server endpoint (defaults to localhost if not set)
# ---------------------------------------------------------------------------
def _get_endpoint() -> str:
    """Return the base URL for the DeusData Codebase‑Memory‑MCP API.

    The environment variable ``DEUSDATA_ENDPOINT`` can be used to override the
    default ``http://127.0.0.1:8000``.
    """
    return os.getenv("DEUSDATA_ENDPOINT", "http://127.0.0.1:8000")

# ---------------------------------------------------------------------------
# Main plugin entry point
# ---------------------------------------------------------------------------
def run(parameters: dict, player=None, session_memory=None) -> str:
    """Execute a code‑intelligence query against the DeusData server.

    Parameters
    ----------
    parameters: dict
        Must contain ``query`` (str) and ``codebase_id`` (str).
    player, session_memory: optional, ignored for this plugin.

    Returns
    -------
    str
        A short, user‑friendly answer that will be spoken by JARVIS. In case of
        any error a brief error description is returned instead of raising.
    """
    try:
        query = parameters.get("query", "").strip()
        codebase_id = parameters.get("codebase_id", "").strip()
        if not query or not codebase_id:
            return "Error: both 'query' and 'codebase_id' must be provided."

        payload = {
            "codebase_id": codebase_id,
            "query": query,
            "max_results": 1  # we only need a concise answer
        }
        endpoint = _get_endpoint().rstrip('/') + "/api/v1/query"
        response = requests.post(endpoint, json=payload, timeout=2)
        response.raise_for_status()
        data = response.json()
        # Assume the server returns {"answer": "..."}
        answer = data.get("answer") or data.get("result") or ""  # fallback keys
        if not answer:
            return "I couldn't find an answer for that query."
        # Keep the spoken string short – truncate to 250 chars and strip.
        short_answer = answer.strip().replace("\n", " ")
        if len(short_answer) > 250:
            short_answer = short_answer[:247] + "..."
        return short_answer
    except requests.exceptions.RequestException as e:
        return f"Network error while contacting the code intelligence service: {str(e)}"
    except json.JSONDecodeError:
        return "Received an invalid response from the code intelligence service."
    except Exception as e:
        # Catch‑all to guarantee we never raise out of the plugin.
        return f"An unexpected error occurred: {str(e)}"
