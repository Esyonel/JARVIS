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
    """Perform a lightweight web search using DuckDuckGo's lite endpoint and
    return a short summary. Raises an exception on any failure — the caller
    falls back to the multi-provider LLM pool (core.ai_text) when this fails,
    e.g. when DuckDuckGo returns its bot-check page instead of real results.
    """
    try:
        import requests
        from bs4 import BeautifulSoup
    except Exception:
        raise RuntimeError("Required libraries 'requests' and 'beautifulsoup4' are not installed.")

    # lite.duckduckgo.com serves plain result links with far less aggressive
    # bot-detection than duckduckgo.com/html/, which now answers automated
    # requests with a 202 "anomaly" page instead of real results.
    search_url = "https://lite.duckduckgo.com/lite/"
    params = {"q": query}
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    resp = requests.get(search_url, params=params, headers=headers, timeout=10)
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")
    result = soup.find("a", {"class": "result-link"}) or soup.find("a", {"class": "result__a"})
    if not result:
        raise RuntimeError("No search results found.")
    title = result.get_text(strip=True)
    url = result.get("href")
    if url.startswith("/l/?"):
        from urllib.parse import parse_qs, urlparse, unquote
        qs = parse_qs(urlparse(url).query)
        if "uddg" in qs:
            url = unquote(qs["uddg"][0])
    return f"{title} ({url})"


def _persist(query: str, summary: str) -> None:
    """Save the result into the shared vector knowledge base (same ChromaDB
    collection plugins/vector_memory_rag.py searches) so JARVIS can recall it
    later via search_memory instead of re-researching the same topic."""
    try:
        import uuid
        import chromadb
        from pathlib import Path

        chroma_dir = Path(__file__).resolve().parent.parent / "memory" / "chroma_db"
        chroma_dir.mkdir(parents=True, exist_ok=True)
        client     = chromadb.PersistentClient(path=str(chroma_dir))
        collection = client.get_or_create_collection(name="jarvis_knowledge")
        collection.add(
            documents=[summary],
            metadatas=[{"source": "internet_research_self_improve", "query": query}],
            ids=[str(uuid.uuid4())[:8]],
        )
    except Exception as e:
        print(f"[internet_research_self_improve] persist failed: {e}")


def _llm_fallback(query: str) -> str:
    """Ask the multi-provider LLM pool (groq → cerebras → openrouter → Gemini
    key rotation, see core/ai_text.py) to research the topic directly. Used
    when the DuckDuckGo scrape fails, so self-improvement research doesn't
    dead-end on a single blocked search engine."""
    from core.ai_text import generate
    prompt = (
        f"Briefly research and summarize what you know about: {query}\n"
        "Answer in 2-3 concise sentences, factual, no preamble."
    )
    return generate(prompt).strip()


def run(parameters: dict, player=None, session_memory=None) -> str:
    """Entry point for the plugin.
    Parameters:
        parameters (dict): Must contain a "query" key with the search string.
        player: Optional audio player (unused).
        session_memory: Optional session memory (unused).
    Returns:
        str: A short spoken response.
    """
    query = parameters.get("query", "").strip()
    if not query:
        return "I couldn't perform the search because no query was provided."

    try:
        summary = _simple_search(query)
        _persist(query, summary)
        return f"I searched the internet for '{query}'. Here’s a brief result: {summary}. I've incorporated this knowledge for future interactions."
    except Exception as search_err:
        try:
            summary = _llm_fallback(query)
            _persist(query, summary)
            return f"I researched '{query}'. Here's what I found: {summary}. I've incorporated this knowledge for future interactions."
        except Exception:
            print(f"[internet_research_self_improve] search failed: {search_err}")
            traceback.print_exc()
            return "I ran into an issue while trying to research that topic. Please try again later."
