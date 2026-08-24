"""
Günlük API kullanım sayacı — hangi sağlayıcının ne kadar kotası kaldığını
gösterebilmek için.

Neden yerel sayaç: Gemini de, Groq/Cerebras/OpenRouter de kalan kotayı API
üzerinden bildirmiyor. Tek dürüst yol yaptığımız çağrıları saymak ve bilinen
günlük limite oranlamak. Yani gösterilen yüzde "sağlayıcının söylediği" değil,
"bizim saydığımız" — JARVIS dışında aynı anahtarı başka bir program da
kullanıyorsa gerçek kalan kota bundan düşük olur.

Sayaçlar tarihe göre tutulur ve gün değişince kendiliğinden sıfırlanır.
"""

import json
import threading
from datetime import date
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
USAGE_PATH = BASE_DIR / "memory" / "api_usage.json"

_lock = threading.Lock()

# Bilinen ücretsiz kademe günlük limitleri. Kesin değerler sağlayıcı ve plana
# göre değişir; yüzde bir tahmindir, faturalandırma verisi değildir.
DAILY_LIMITS = {
    "gemini": 20,        # generate_content, ücretsiz kademe
    "gemini_live": 20,   # canlı ses oturumu ayrı sayılır
    "groq": 1000,
    "cerebras": 1000,
    "openrouter": 50,
    "nvidia_integrate": 1000,  # NVIDIA Integrate API, ücretsiz tier
    "nvidia_vision": 500,       # NVIDIA Vision API, ücretsiz tier
}

_last_used: str = ""


def _load() -> dict:
    try:
        data = json.loads(USAGE_PATH.read_text(encoding="utf-8"))
        if data.get("date") == date.today().isoformat():
            return data
    except Exception:
        pass
    return {"date": date.today().isoformat(), "counts": {}}


def _save(data: dict) -> None:
    try:
        USAGE_PATH.parent.mkdir(parents=True, exist_ok=True)
        USAGE_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as e:
        print(f"[ApiUsage] kaydedilemedi: {e}")


def record(label: str) -> None:
    """Bir çağrıyı say ve bunu 'şu an aktif olan' sağlayıcı yap."""
    global _last_used
    with _lock:
        data = _load()
        data["counts"][label] = data["counts"].get(label, 0) + 1
        _save(data)
        _last_used = label


def active() -> str:
    """Son başarılı çağrıyı yapan sağlayıcının etiketi."""
    return _last_used


def used(label: str) -> int:
    with _lock:
        return _load()["counts"].get(label, 0)


def remaining_pct(label: str) -> int | None:
    """Bilinen limite göre kalan yüzde; limiti bilinmeyen için None."""
    base = label.split("-")[0] if label.startswith("gemini-") else label
    limit = DAILY_LIMITS.get(base)
    if not limit:
        return None
    left = max(0, limit - used(label))
    return int(round(left / limit * 100))


def snapshot(gemini_key_count: int) -> list[dict]:
    """Arayüzün çizeceği satırlar: her sağlayıcı için etiket, yüzde, aktif mi.

    Gemini anahtarları gemini-1..gemini-N olarak ayrı ayrı listelenir, çünkü
    her anahtarın kotası bağımsızdır ve önemli olan hangisinde yer kaldığı.
    """
    rows: list[dict] = []
    current = active()

    for i in range(1, max(gemini_key_count, 1) + 1):
        label = f"gemini-{i}"
        rows.append({
            "label": label,
            "pct": remaining_pct(label),
            "active": current == label,
        })

    for name in ("openrouter", "groq", "cerebras", "nvidia_integrate"):
        rows.append({
            "label": name,
            "pct": remaining_pct(name),
            "active": current == name,
        })

    return rows
