import requests
import re

PLUGIN = {
    "name": "deep_web_search",
    "description": "İnternette derin arama yapar ve özet sonuçlar döndürür.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "query": {
                "type": "string",
                "description": "Aranacak metin"
            },
            "depth": {
                "type": "integer",
                "description": "Arama derinliği (tekrarlama sayısı)"
            }
        },
        "required": ["query"]
    }
}

def _fetch_results(query: str) -> list:
    """Fetch a few result titles from DuckDuckGo HTML search.
    Returns a list of title strings (max 5)."""
    try:
        url = "https://duckduckgo.com/html/"
        resp = requests.get(url, params={"q": query}, timeout=5, headers={"User-Agent": "Mozilla/5.0"})
        resp.raise_for_status()
        html = resp.text
        # Find result titles
        titles = re.findall(r'<a[^>]*class="result__a"[^>]*>(.*?)</a>', html, re.IGNORECASE | re.DOTALL)
        # Clean HTML tags from titles
        clean_titles = []
        for t in titles[:5]:
            clean = re.sub(r'<.*?>', '', t)
            clean = re.sub(r'\s+', ' ', clean).strip()
            clean_titles.append(clean)
        return clean_titles
    except Exception:
        return []

def run(parameters: dict, player=None, session_memory=None) -> str:
    """Perform a deep web search.
    Parameters:
        query (str): search query (required)
        depth (int, optional): how many times to repeat the search for deeper results.
    Returns:
        A short plain Turkish sentence summarizing the top results.
    """
    try:
        query = parameters.get("query", "").strip()
        if not query:
            return "Arama için bir sorgu belirtmelisin."
        depth = parameters.get("depth", 1)
        try:
            depth = int(depth)
        except Exception:
            depth = 1
        if depth < 1:
            depth = 1
        all_titles = []
        for _ in range(depth):
            titles = _fetch_results(query)
            if not titles:
                break
            all_titles.extend(titles)
        if not all_titles:
            return f""""{query}""" için sonuç bulunamadı."""
        # Remove duplicates while preserving order
        seen = set()
        unique_titles = []
        for t in all_titles:
            if t not in seen:
                seen.add(t)
                unique_titles.append(t)
        # Take up to 5 titles for brevity
        summary = ", ".join(unique_titles[:5])
        return f""""{query}""" için bulduğum ilk sonuçlar: {summary}."""
    except Exception as e:
        return f"Derin arama sırasında bir hata oluştu: {str(e)}"
