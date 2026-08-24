PLUGIN = {
    "name": "web_scraper",
    "description": "Herhangi bir web sitesinden veri kazıma (web scraping) yeteneği. URL ve isteğe bağlı CSS seçicisi (selector) alır ve sayfanın metin içeriğini döndürür.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "url": {
                "type": "string",
                "description": "Kazımak istediğiniz web sayfasının tam URL'i."
            },
            "selector": {
                "type": "string",
                "description": "İsteğe bağlı CSS seçicisi. Belirtilirse sadece bu seçiciye uyan elementlerin metni alınır."
            }
        },
        "required": ["url"]
    }
}

def run(parameters: dict, player=None, session_memory=None) -> str:
    """Web sayfasını indirir ve belirtilen CSS seçicisine göre metni çıkarır.

    Args:
        parameters: {'url': str, 'selector': str (optional)}
        player: (unused) Ses oynatıcı, JARVIS içinde kullanılabilir.
        session_memory: (unused) Oturum hafızası, gerektiğinde kullanılabilir.
    Returns:
        Kısa bir metin mesajı. Başarılı ise çıkarılan veri (ilk 500 karakter),
        hata oluştuysa hata mesajı.
    """
    try:
        import requests
        from bs4 import BeautifulSoup
    except Exception as e:
        return f"Web kazıma için gerekli kütüphaneler eksik: {e}"  # noqa: E501

    url = parameters.get("url", "").strip()
    selector = parameters.get("selector")

    if not url:
        return "Web kazıma hatası: URL parametresi boş."

    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
    except Exception as e:
        return f"Web sayfasına erişilemedi: {e}"

    try:
        soup = BeautifulSoup(response.text, "html.parser")
        if selector:
            elements = soup.select(selector)
            if not elements:
                return f"Seçiciyle eşleşen öğe bulunamadı: {selector}"
            extracted = "\n".join([el.get_text(strip=True) for el in elements])
        else:
            extracted = soup.get_text(separator="\n", strip=True)
        # Çok uzun çıktıyı kısalt
        preview = extracted[:500].replace("\n", " ")
        if len(extracted) > 500:
            preview += " ... (devamı kesildi)"
        return f"Web sayfasından veri kazıma tamamlandı. Özet: {preview}"
    except Exception as e:
        return f"Web sayfasını işleme sırasında hata oluştu: {e}"
