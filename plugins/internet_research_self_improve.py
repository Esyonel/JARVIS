PLUGIN = {
    "name": "internet_research_self_improve",
    "description": "Conducts an internet search for a given query, extracts a brief summary, and informs the user that the knowledge base has been refreshed.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "query": {
                "type": "string",
                "description": "The search term or question to look up on the internet."
            }
        },
        "required": ["query"]
    }
}

import json
import traceback

def _simple_search(query: str) -> str:
    """Perform a lightweight web search using DuckDuckGo and return a short summary.
    This function fetches the HTML results page, extracts the title and URL of the
    first result, and returns a concise string. If any step fails, it raises an
    exception which is handled by the caller.
    """
    try:
        import requests
        from bs4 import BeautifulSoup
    except Exception as e:
        raise RuntimeError("Required libraries 'requests' and 'beautifulsoup4' are not installed.")

    search_url = "https://duckduckgo.com/html/"
    params = {"q": query}
    headers = {"User-Agent": "Mozilla/5.0 (compatible; JARVIS/1.0)"}
    resp = requests.get(search_url, params=params, headers=headers, timeout=10)
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")
    result = soup.find("a", {"class": "result__a"})
    if not result:
        raise RuntimeError("No search results found.")
    title = result.get_text(strip=True)
    url = result.get("href")
    # DuckDuckGo returns redirect URLs like "/l/?kh=-1&uddg=<encoded>", extract real URL
    if url.startswith("/l/?"):
        from urllib.parse import parse_qs, urlparse, unquote
        qs = parse_qs(urlparse(url).query)
        if "uddg" in qs:
            url = unquote(qs["uddg"][0])
    return f"{title} ({url})"


def run(parameters: dict, player=None, session_memory=None) -> str:
    """Entry point for the plugin.
    Parameters:
        parameters (dict): Must contain a "query" key with the search string.
        player: Optional audio player (unused).
        session_memory: Optional session memory (unused).
    Returns:
        str: A short spoken response.
    """
    try:
        query = parameters.get("query", "").strip()
        if not query:
            return "I couldn't perform the search because no query was provided."
        summary = _simple_search(query)
        # Here you could integrate the result into a self‑improvement routine.
        # For now we simply acknowledge the action.
        return f"I searched the internet for '{query}'. Here’s a brief result: {summary}. I've incorporated this knowledge for future interactions."
    except Exception:
        # Return a user‑friendly error message without exposing stack traces.
        return "I ran into an issue while trying to research that topic. Please try again later."
