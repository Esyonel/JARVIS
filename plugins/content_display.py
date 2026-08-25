import requests
from bs4 import BeautifulSoup

# Plugin metadata used by the JARVIS core to discover and describe plugins.
PLUGIN = {
    "name": "content_display",
    "description": "Kullanıcının belirttiği URL üzerinden gazete, makale ya da başka bir web içeriğini çeker ve JARVIS arayüzünde gösterir.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "url": {
                "type": "string",
                "description": "İçeriğin bulunduğu tam URL."
            },
            "max_chars": {
                "type": "integer",
                "description": "Dönüşte kaç karakter gösterileceği. Varsayılan 2000."
            }
        },
        "required": ["url"]
    }
}

def _extract_text(html: str) -> str:
    """Basit bir metin çıkarımı. HTML etiketlerini kaldırır ve okunabilir metin döndürür.
    
    Eğer BeautifulSoup yüklü değilse, ham HTML döndürülür.
    """
    try:
        soup = BeautifulSoup(html, "html.parser")
        # Görünür metin bloklarını al (paragraflar, başlıklar vs.)
        texts = []
        for element in soup.find_all(["p", "h1", "h2", "h3", "h4", "h5", "h6", "li"]):
            txt = element.get_text(strip=True)
            if txt:
                texts.append(txt)
        return "\n".join(texts) if texts else soup.get_text(separator="\n", strip=True)
    except Exception:
        # Fallback: döndürülmüş ham HTML
        return html

def run(parameters: dict, player=None, session_memory=None) -> str:
    """Kullanıcıdan gelen parametrelerle içeriği alır ve kısa bir özetini döndürür.
    
    Args:
        parameters: {'url': str, 'max_chars': int (opsional)}
        player: Sesli çıktı oynatıcı (kullanılmaz, ama imzaya uymak için burada).
        session_memory: Oturum belleği (kullanılmaz).
    
    Returns:
        İçeriğin ilk *max_chars* karakteriyle bir mesaj. Hata durumunda açıklayıcı bir metin.
    """
    url = parameters.get("url")
    max_chars = parameters.get("max_chars", 2000)

    if not url:
        return "URL parametresi eksik. Lütfen geçerli bir web adresi sağlayın."

    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        content = _extract_text(response.text)
        if not content:
            return "İçerik bulunamadı veya metin olarak çıkarılamadı."
        # Kullanıcı deneyimi için çok uzun metinleri kırp
        trimmed = content[:max_chars]
        if len(content) > max_chars:
            trimmed += "... (devamı kesildi)"
        return trimmed
    except requests.exceptions.RequestException as e:
        return f"Web sitesine erişilemedi: {str(e)}"
    except Exception as e:
        return f"İçerik getirirken beklenmeyen bir hata oluştu: {str(e)}"
