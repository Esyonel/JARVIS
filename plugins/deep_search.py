'''Deep Search Plugin

Provides an advanced internet search capability that goes beyond a single
query result. The plugin fetches the top search results, extracts a short
snippet from each, and returns a concise summary that can be spoken by JARVIS.

The implementation is deliberately lightweight: it performs a standard web
search using DuckDuckGo's HTML interface (no API key required) and extracts the
first few result titles and URLs. If any step fails, a user‑friendly error
message is returned.
'''

import requests
from bs4 import BeautifulSoup
from typing import Dict, Any

# ---------------------------------------------------------------------------
# Plugin metadata – JARVIS discovers plugins by inspecting this dict.
# ---------------------------------------------------------------------------
PLUGIN = {
    "name": "deep_search",
    "description": "Performs an in‑depth internet search and returns a brief spoken summary.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "query": {
                "type": "string",
                "description": "The search phrase to look up on the internet"
            }
        },
        "required": ["query"]
    }
}

# ---------------------------------------------------------------------------
# Helper: fetch top results from DuckDuckGo (HTML version).
# ---------------------------------------------------------------------------
def _fetch_duckduckgo_results(query: str, max_results: int = 3) -> list[dict[str, str]]:
    """Return a list of dictionaries with 'title' and 'url' keys.

    The function performs a GET request to DuckDuckGo's HTML search page and
    parses the result snippets. It is tolerant to network issues – any exception
    is bubbled up to the caller for handling.
    """
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        )
    }
    params = {"q": query, "ia": "web"}
    response = requests.get("https://html.duckduckgo.com/html/", params=params, headers=headers, timeout=10)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")
    results = []
    for result in soup.select("div.result")[:max_results]:
        a_tag = result.select_one("a.result__a")
        if not a_tag:
            continue
        title = a_tag.get_text(strip=True)
        url = a_tag.get("href", "").strip()
        results.append({"title": title, "url": url})
    return results

# ---------------------------------------------------------------------------
# Main entry point used by JARVIS.
# ---------------------------------------------------------------------------
def run(parameters: Dict[str, Any], player=None, session_memory=None) -> str:
    """Execute the deep search.

    Parameters
    ----------
    parameters: dict
        Must contain a ``query`` key as defined in the PLUGIN metadata.
    player, session_memory: optional – kept for signature compatibility.

    Returns
    -------
    str
        A short plain‑text sentence that JARVIS will speak aloud.
    """
    try:
        query = parameters.get("query", "").strip()
        if not query:
            return "I couldn't perform the deep search because the query was empty."

        # Fetch top results.
        results = _fetch_duckduckgo_results(query)
        if not results:
            return f"I couldn't find any results for '{query}'."

        # Build a concise spoken summary.
        titles = ", ".join([r["title"] for r in results])
        summary = f"Here are the top results for {query}: {titles}."
        return summary
    except requests.RequestException:
        return "I ran into a network issue while trying to search the internet. Please check your connection and try again."
    except Exception as exc:
        # Catch‑all to ensure the plugin never crashes the assistant.
        return f"An unexpected error occurred during the deep search: {str(exc)}"
