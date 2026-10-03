"""
market_watch/analysis.py — yeni haber başlıkları için kısa "piyasaya etkisi"
yorumu üretir.

JARVIS'in actions/nvidia_integrate_api.py ile aynı NVIDIA Integrate API
desenini (https://integrate.api.nvidia.com/v1/chat/completions,
minimaxai/minimax-m3) kullanır — yeni bir bağımlılık eklemez, requests
zaten JARVIS'in requirements.txt'inde var. API'ye erişilemezse sessizce
hiçbir şey eklemez (bu adım opsiyonel bir zenginleştirme, ana brifing
akışını asla bloklamaz/çökertmez).
"""
from __future__ import annotations

import json

import requests

_INVOKE_URL = "https://integrate.api.nvidia.com/v1/chat/completions"
# minimaxai/minimax-m3 09.09.2026'da NVIDIA katalogundan tamamen kaldırıldı
# (end-of-life, 410 Gone) — yerine hızlı/hafif nvidia/nemotron-3.5-lightning
# kullanılıyor. "enable_thinking: False" olmadan bu model önce uzun bir
# muhakeme (reasoning_content) metni üretiyor ve JSON çıktısı gecikiyor/
# kesiliyor; kapatınca doğrudan nihai cevabı veriyor.
_MODEL = "nvidia/nemotron-3.5-lightning-30b-a3b"


def add_impact_analysis(headlines: list[dict]) -> None:
    """headlines listesindeki her sözlüğe mümkünse 'impact' alanı ekler
    (Türkçe, tek cümle, TL/altın/borsa/faiz üzerindeki olası etkiyi anlatır).
    Liste yerinde (in-place) değiştirilir; başarısızlıkta hiçbir şey eklenmez."""
    if not headlines:
        return

    from memory.config_manager import load_api_keys

    api_key = load_api_keys().get("nvidia_integrate_api_key")
    if not api_key:
        return

    items_text = "\n".join(
        f"{i + 1}. [{h['topic']}] {h['title']} — {h.get('snippet', '')}"
        for i, h in enumerate(headlines)
    )
    prompt = (
        "Aşağıda finans/piyasa haber başlıkları listelendi. Her biri için, bu "
        "haberin Türkiye piyasalarını (TL, altın, gümüş, borsa, faiz oranları) "
        "NASIL ETKİLEYEBİLECEĞİNİ, GRAMER OLARAK TAM ve akıcı, tek bir Türkçe "
        "cümleyle açıkla. Cümle sıra numarası veya haber başlığını TEKRARLAMASIN, "
        "doğrudan yorumla başlasın. En fazla iki etkiye odaklan, yarım bırakma. "
        "Makul ama temkinli bir dil kullan ('...etkileyebilir', '...baskı "
        "yaratabilir' gibi), kesin öngörüde bulunma.\n\n"
        f"{items_text}\n\n"
        "Örnek stil: \"Faiz artışı TL'yi kısa vadede destekleyebilir ancak "
        "borsada kâr satışlarını tetikleyebilir.\"\n\n"
        "Yanıtı SADECE şu JSON formatında ver, başka hiçbir açıklama ekleme: "
        '{"impacts": ["<1. haberin yorumu, tam cümle>", "<2. haberin yorumu, tam cümle>", ...]}'
    )

    try:
        resp = requests.post(
            _INVOKE_URL,
            headers={"Authorization": f"Bearer {api_key}", "Accept": "application/json"},
            json={
                "model": _MODEL,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.4,
                "top_p": 0.9,
                "max_tokens": 1024,
                "stream": False,
                "chat_template_kwargs": {"enable_thinking": False},
            },
            timeout=30,
        )
        resp.raise_for_status()
        content = resp.json()["choices"][0]["message"]["content"].strip()

        try:
            from core.api_usage import record as record_api_usage
            record_api_usage("nvidia-1")
        except Exception:
            pass

        content = content.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        # Model bazen JSON'dan önce/sonra ek metin ekleyebilir — ilk { ile son } arasını al.
        start, end = content.find("{"), content.rfind("}")
        if start != -1 and end != -1:
            content = content[start:end + 1]

        impacts = json.loads(content).get("impacts", [])
        for h, impact in zip(headlines, impacts):
            if impact:
                h["impact"] = impact
    except Exception as e:
        print(f"[market_watch.analysis] ⚠️ Etki analizi üretilemedi: {e}")
