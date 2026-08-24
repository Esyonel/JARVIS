PLUGIN = {
    "name": "web_experience_browser",
    "description": "Kullanıcının mevcut tarayıcı oturumunu ve kimlik doğrulamalarını koruyarak, verilen URL'yi yeni bir sekmede açar. Böylece kullanıcı, web sitelerine kendi deneyimi gibi erişebilir.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "url": {
                "type": "string",
                "description": "Açılacak web sayfasının tam URL'i."
            }
        },
        "required": ["url"]
    }
}

import webbrowser
import re

def _is_valid_url(url: str) -> bool:
    """Basit URL doğrulaması."""
    # http/https ile başlamalı ve temel bir yapı kontrolü yapar.
    pattern = re.compile(r'^(https?://)[\w.-]+(?:\.[\w.-]+)+[\w\-.,@?^=%&:/~+#]*$')
    return bool(pattern.match(url))

def run(parameters: dict, player=None, session_memory=None) -> str:
    """Kullanıcının mevcut tarayıcı oturumunu koruyarak URL'yi açar.

    Args:
        parameters: {'url': 'https://example.com'}
        player: (isteğe bağlı) ses oynatıcı, burada kullanılmaz.
        session_memory: (isteğe bağlı) eğer plugin hafıza kullanıyorsa, burada kullanılmaz.
    Returns:
        Kullanıcıya sesli olarak okunacak kısa bir mesaj.
    """
    try:
        url = parameters.get("url", "").strip()
        if not url:
            return "URL parametresi eksik. Lütfen bir web adresi sağlayın."
        if not _is_valid_url(url):
            return "Sağladığınız URL geçerli değil. Lütfen http veya https ile başlayan tam bir adres girin."
        # webbrowser modülü, sistemdeki varsayılan tarayıcıyı kullanıcı profiliyle birlikte
        # açar, böylece oturum çerezleri ve kimlik doğrulamalar korunur.
        opened = webbrowser.open_new_tab(url)
        if opened:
            return f"Web sayfası açıldı: {url}"
        else:
            return "Web sayfası açılamadı. Tarayıcı ayarlarınızı kontrol edin."
    except Exception as e:
        # Hata mesajını çok detaylı vermek yerine, kullanıcı dostu bir mesaj döndürürüz.
        return f"Web sayfasını açarken bir hata oluştu: {str(e)}"
