import os
import random
import re
import requests
from collections import Counter
from io import BytesIO
from typing import Dict

from PIL import Image, ImageDraw, ImageFont
from bs4 import BeautifulSoup

# Simple stop‑words list (English & Turkish common words). Extend as needed.
_STOPWORDS = {
    "the", "and", "a", "an", "of", "to", "in", "for", "on", "with",
    "that", "this", "is", "are", "was", "were", "be", "by", "as",
    "at", "or", "it", "from", "but", "not", "we", "you", "i", "he",
    "she", "they", "his", "her", "their", "our", "my", "me", "us",
    # Turkish stop‑words
    "ve", "bu", "için", "bir", "da", "de", "ile", "ki", "gibi", "en",
    "çok", "daha", "ile", "ama", "ise", "veya", "ya", "ya da", "kadar",
    "son", "ilk", "şu", "o", "bu", "her", "kendi", "hangi",
}

PLUGIN = {
    "name": "web_keyword_analyzer",
    "description": "Belirtilen bir web sayfasının metnini çeker, kelime sıklığını yüzde olarak hesaplar ve Pillow ile kelime bulutu görseli oluşturur.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "url": {
                "type": "STRING",
                "description": "Analiz edilecek web sayfasının tam URL'i"
            },
            "top_n": {
                "type": "INTEGER",
                "description": "Word‑cloud içinde gösterilecek en sık kullanılan kelime sayısı (varsayılan 20)"
            }
        },
        "required": ["url"]
    }
}


def _fetch_text(url: str) -> str:
    """Fetches the page and returns plain text content.
    Returns an empty string on failure.
    """
    try:
        resp = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        # Remove script/style elements
        for tag in soup(["script", "style", "noscript"]):
            tag.decompose()
        text = soup.get_text(separator=" ")
        return text
    except Exception as e:
        return ""


def _clean_and_tokenize(text: str) -> list:
    # Lowercase, keep only word characters, filter stop‑words
    words = re.findall(r"\b\w+\b", text.lower())
    filtered = [w for w in words if w not in _STOPWORDS and len(w) > 1]
    return filtered


def _create_wordcloud(word_percents: Dict[str, float], output_path: str) -> None:
    # Basic word‑cloud: random placement, font size proportional to percentage.
    width, height = 800, 600
    image = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(image)

    # Try to load a truetype font; fall back to default.
    try:
        font_path = ImageFont.truetype("arial.ttf", 10).path
    except Exception:
        font_path = None

    for word, percent in word_percents.items():
        # Font size: 15‑100 based on percent (scale factor can be tuned)
        size = int(15 + percent * 5)
        try:
            font = ImageFont.truetype(font_path, size) if font_path else ImageFont.load_default()
        except Exception:
            font = ImageFont.load_default()
        # Random position; ensure we stay inside canvas.
        w, h = draw.textsize(word, font=font)
        x = random.randint(0, max(0, width - w))
        y = random.randint(0, max(0, height - h))
        # Random dark color for visibility.
        color = tuple(random.randint(0, 150) for _ in range(3))
        draw.text((x, y), word, fill=color, font=font)

    # Save image
    image.save(output_path)


def run(parameters: dict, player=None, session_memory=None) -> str:
    """Main entry point for the plugin.
    Returns a short spoken summary. Errors are caught and reported as plain text.
    """
    url = parameters.get("url", "").strip()
    top_n = parameters.get("top_n", 20)
    if not url:
        return "Web analizi için geçerli bir URL belirtilmedi."
    try:
        text = _fetch_text(url)
        if not text:
            return f"{url} adresinden içerik alınamadı veya sayfa boş."
        words = _clean_and_tokenize(text)
        if not words:
            return "Sayfada analiz edilebilecek kelime bulunamadı."
        counter = Counter(words)
        total = sum(counter.values())
        most_common = counter.most_common(top_n)
        # Compute percentages
        word_percents = {word: (count / total) * 100 for word, count in most_common}

        # Prepare output image path (inside a temporary directory)
        temp_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "tmp"))
        os.makedirs(temp_dir, exist_ok=True)
        image_path = os.path.join(temp_dir, "web_keyword_wordcloud.png")
        _create_wordcloud(word_percents, image_path)

        # Build spoken summary (list top 3 for brevity)
        top_items = ", ".join([f"{w} (%{p:.1f})" for w, p in most_common[:3]])
        return f"Web sayfası analiz edildi. En sık kullanılan kelimeler: {top_items}. Kelime bulutu oluşturuldu ve {image_path} yolunda kaydedildi."
    except Exception as exc:
        # Generic safeguard – never raise to caller.
        return f"Web anahtar kelime analizi sırasında bir hata oluştu: {str(exc)}"
