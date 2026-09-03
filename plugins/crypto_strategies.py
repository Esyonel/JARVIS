PLUGIN = {
    "name": "crypto_strategies",
    "description": "Provides new cryptocurrency trading strategies and brief guidance.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "strategy": {
                "type": "string",
                "description": "Name of the strategy you want information about (e.g., mean_reversion, breakout, grid, arbitrage)."
            },
            "risk_level": {
                "type": "string",
                "description": "Risk tolerance: low, medium, high."
            }
        },
        "required": []
    }
}

def run(parameters: dict, player=None, session_memory=None) -> str:
    """Return a short spoken description of the requested crypto strategy.

    The function never raises; any error is caught and a user‑friendly message
    is returned. The output is a plain string suitable for JARVIS to speak.
    """
    try:
        strategy = parameters.get("strategy", "").strip().lower()
        risk = parameters.get("risk_level", "").strip().lower()
        if not strategy:
            return "Lütfen öğrenmek istediğiniz kripto stratejisini belirtin."

        # Simple static explanations – real implementation can be expanded.
        if strategy == "mean_reversion":
            return "Mean Reversion stratejisi, fiyatların ortalama seviyeye geri döneceği varsayımına dayanır; düşük volatilite ve düşük risk seviyesinde uygundur."
        if strategy == "breakout":
            return "Breakout stratejisi, fiyatın önemli bir destek/direnç seviyesini kırdığında pozisyon açar; yüksek volatilite ve yüksek risk toleransı gerektirir."
        if strategy == "grid":
            return "Grid stratejisi, fiyat aralığında otomatik olarak alım‑satım emirleri yerleştirir; orta risk ve sürekli piyasa hareketi olan paritelerde etkilidir."
        if strategy == "arbitrage":
            return "Arbitraj stratejisi, farklı borsalar arasındaki fiyat farklarından faydalanır; teknik altyapı ve hızlı işlem gerektirir."

        # Fallback for unknown strategies.
        return f"{strategy.capitalize()} adlı strateji hakkında bilgi bulunamadı. Başka bir strateji deneyin."
    except Exception as e:
        return f"Kripto strateji bilgisi alınırken bir hata oluştu: {str(e)}"
