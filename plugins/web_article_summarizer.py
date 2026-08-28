"""Web Article Summarizer Plugin

Fetches an article from a given URL, extracts the main textual content using
BeautifulSoup, and returns a concise summary consisting of a few sentences.
"""

import re
from typing import Any, Dict

import requests
from bs4 import BeautifulSoup

# Plugin metadata consumed by the JARVIS plugin loader
PLUGIN = {
    "name": "web_article_summarizer",
    "description": "Summarizes the main content of a web article from a given URL into a short few‑sentence summary.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "url": {
                "type": "string",
                "description": "The URL of the article to summarize."
            }
        },
        "required": ["url"]
    }
}


def _extract_text(html: str) -> str:
    """Extract readable text from HTML.

    The function removes script/style elements, gathers visible paragraph text,
    and collapses whitespace.
    """
    soup = BeautifulSoup(html, "html.parser")
    for element in soup(["script", "style", "noscript"]):
        element.decompose()
    paragraphs = [p.get_text(separator=" ", strip=True) for p in soup.find_all("p")]
    # Fallback to full body text if no paragraphs found
    if not paragraphs:
        body = soup.body
        if body:
            paragraphs = [body.get_text(separator=" ", strip=True)]
    text = " ".join(paragraphs)
    # Collapse multiple spaces/newlines
    return re.sub(r"\s+", " ", text).strip()


def _summarize(text: str, max_sentences: int = 3) -> str:
    """Return the first *max_sentences* sentences from *text*.

    A very lightweight summarizer – it simply splits on sentence‑ending punctuation
    and returns the leading sentences. If fewer sentences are present, the whole
    text is returned.
    """
    # Regex that captures sentence boundaries (handles ?, !, .) followed by space or end
    sentence_endings = re.compile(r"(?<=[.!?])\s+")
    sentences = sentence_endings.split(text)
    summary = " ".join(sentences[:max_sentences])
    # Ensure the summary ends with a period for a clean spoken output
    if summary and not summary.endswith(('.', '!', '?')):
        summary += '.'
    return summary


def run(parameters: Dict[str, Any], player=None, session_memory=None) -> str:
    """Execute the plugin.

    Parameters
    ----------
    parameters: dict
        Must contain the key ``"url"`` with a string value.
    player, session_memory: optional
        Ignored by this plugin but kept for compatibility with the JARVIS
        plugin interface.

    Returns
    -------
    str
        A short summary of the article or an error description.
    """
    url = parameters.get("url")
    if not isinstance(url, str) or not url:
        return "Error: 'url' parameter is missing or not a valid string."
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
    except Exception as exc:
        return f"Error: Unable to retrieve the article – {exc}."
    try:
        article_text = _extract_text(response.text)
        if not article_text:
            return "Error: Could not extract any readable content from the page."
        summary = _summarize(article_text)
        return summary
    except Exception as exc:
        return f"Error: An unexpected problem occurred while summarizing – {exc}."
