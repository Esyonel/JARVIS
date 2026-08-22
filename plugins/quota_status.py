"""
JARVIS plugin — API kota ve sağlayıcı durumu.

Gemini anahtar havuzunda kaç anahtar kaldığını ve hangi yedek sağlayıcıların
yapılandırıldığını söyler. Sesin neden sustuğunu anlamanın en hızlı yolu bu:
canlı ses yalnızca Gemini'de çalıştığı için, havuzdaki anahtarlar tükendiğinde
JARVIS konuşamaz hale gelir — metin tarafı yedek sağlayıcılarla devam etse bile.
"""

PLUGIN = {
    "name": "quota_status",
    "description": (
        "Reports how many Gemini API keys are still usable today and which "
        "fallback providers are configured. Use for: 'kotam ne durumda', 'kaç "
        "anahtarım kaldı', 'neden konuşamıyorsun', 'API durumu nedir', 'ses "
        "neden çalışmıyor'. Read-only — reports status, changes nothing."
    ),
    "parameters": {"type": "OBJECT", "properties": {}, "required": []},
}


def run(parameters: dict, player=None, session_memory=None) -> str:
    parts = []

    try:
        from core.gemini_keys import all_keys, available_keys
        total = len(all_keys())
        fresh = len([k for k in all_keys() if k in available_keys()])

        if total == 0:
            parts.append("Gemini anahtarı yapılandırılmamış — sesli mod çalışmaz.")
        elif fresh == 0:
            parts.append(
                f"{total} Gemini anahtarının hepsinin günlük kotası dolmuş. "
                "Sesli mod bugün çalışmayabilir; kotalar Google'ın saatinde sıfırlanır."
            )
        else:
            parts.append(f"Gemini: {total} anahtardan {fresh} tanesi bugün hâlâ kullanılabilir.")
    except Exception as e:
        parts.append(f"Gemini anahtar durumu okunamadı: {e}")

    try:
        from core.ai_text import available_providers
        others = [p for p in available_providers() if p != "gemini"]
        if others:
            parts.append(
                "Metin işleri için yedek sağlayıcılar hazır: " + ", ".join(others) + ". "
                "Gemini kotası bitse bile yazılı işler çalışmaya devam eder."
            )
        else:
            parts.append(
                "Yedek sağlayıcı yok — Gemini kotası bitince metin işleri de durur."
            )
    except Exception as e:
        parts.append(f"Sağlayıcı listesi okunamadı: {e}")

    result = " ".join(parts)
    _log(result, player)
    return result


def _log(message: str, player=None) -> None:
    print(f"[QuotaStatus] {message[:250]}")
    if player:
        try:
            player.write_log(f"JARVIS: {message}")
        except Exception:
            pass
