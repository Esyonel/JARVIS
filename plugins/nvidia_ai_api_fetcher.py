import requests
from bs4 import BeautifulSoup

PLUGIN = {
    "name": "nvidia_ai_api_fetcher",
    "description": "Fetches and lists API information of AI programs from Nvidia's developer website.",
    "parameters": {
        "type": "OBJECT",
        "properties": {},
        "required": []
    }
}

def run(parameters: dict, player=None, session_memory=None) -> str:
    """Retrieve a concise list of AI‑related API entries from Nvidia's website.

    The function attempts to download the main AI developer page, extracts
    anchor elements whose visible text or URL contain the word "API", and
    returns a short, readable sentence that can be spoken by the assistant.
    In case of any failure, a user‑friendly error message is returned.
    """
    try:
        url = "https://developer.nvidia.com/ai"
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        api_links = []
        for a in soup.find_all("a", href=True):
            text = (a.get_text(separator=" ") or "").strip()
            href = a["href"].lower()
            if "api" in text.lower() or "api" in href:
                # Resolve relative URLs
                full_url = requests.compat.urljoin(url, a["href"]).strip()
                display = text if text else full_url
                api_links.append(display)
        # De‑duplicate while preserving order
        seen = set()
        unique_links = []
        for item in api_links:
            if item not in seen:
                seen.add(item)
                unique_links.append(item)
        if not unique_links:
            return "I couldn't find any API references on Nvidia's AI page."
        # Limit the spoken output to a reasonable length
        max_items = 5
        listed = ", ".join(unique_links[:max_items])
        if len(unique_links) > max_items:
            listed += ", and more."
        return f"Here are some Nvidia AI APIs I found: {listed}."
    except requests.RequestException as e:
        return f"I had trouble reaching Nvidia's website: {str(e)}."
    except Exception as e:
        return f"An unexpected error occurred while fetching Nvidia AI API information: {str(e)}."
