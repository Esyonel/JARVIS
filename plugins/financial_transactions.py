PLUGIN = {
    "name": "financial_transactions",
    "description": "Finansal işlemler, taksitlendirme ve para yönetimi konularında kullanıcı sorularına yanıt verir.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "query": {
                "type": "string",
                "description": "Kullanıcının finansal işlem, taksitlendirme veya para yönetimi konusundaki sorusu."
            }
        },
        "required": ["query"]
    }
}

def run(parameters: dict, player=None, session_memory=None) -> str:
    """Process financial and installment related queries.

    Args:
        parameters (dict): Must contain a "query" key with the user's request.
        player: Optional audio player (ignored here).
        session_memory: Optional session memory (ignored here).

    Returns:
        str: A short spoken response in Turkish.
    """
    try:
        query = parameters.get("query", "").strip()
        if not query:
            return "Lütfen finansal bir soru veya taksitlendirme talebinizi belirtin."

        lowered = query.lower()
        # Simple keyword‑based handling – can be expanded later.
        if "taksit" in lowered:
            return (
                "Taksitlendirme hakkında bilgi: "
                "Toplam tutarı, taksit sayısını ve faiz oranını belirtirseniz, "
                "size ödeme planı oluşturabilirim."
            )
        if "bakiye" in lowered or "para çek" in lowered or "ödeme" in lowered:
            return (
                "Finansal işlem talebinizi aldım. "
                "Lütfen hesabınızı doğrulayın ve gerekli miktarı girin."
            )
        if "faiz" in lowered or "kredi" in lowered:
            return (
                "Kredi ve faiz hesaplamaları için toplam tutarı, vadeyi ve faiz oranını belirtin, "
                "size detaylı bir ödeme planı sunabilirim."
            )
        # Default fallback
        return "Finansal konularla ilgili yardımcı olabilirim, lütfen detayları paylaşın."
    except Exception as e:
        # Never raise – return a user‑friendly error string.
        return f"Finansal işlem sırasında bir hata oluştu: {str(e)}"
