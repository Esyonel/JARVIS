"""
Gemini anahtar havuzu yöneticisi.

Birden fazla Gemini anahtarını tek oturumda ekler. Her anahtar kaydedilmeden
ÖNCE gerçekten çalışıyor mu diye test edilir — böylece yanlış yapıştırılmış
veya ölü bir anahtar haftalar sonra, tam kotalar tükendiğinde değil, hemen
burada fark edilir.

Neden birden fazla anahtar: canlı ses yalnızca Gemini üzerinden çalışıyor
(başka sağlayıcıda karşılığı yok) ve her ücretsiz anahtarın günlük kotası
küçük. Havuzdaki bir anahtar dolunca sıradakine geçilir.

ÖNEMLİ: Her anahtar FARKLI bir Google hesabından alınmalı. Aynı hesaptan
alınan anahtarlar aynı kotayı paylaşır, havuz işe yaramaz.

Çalıştırma:  .venv\\Scripts\\python.exe gemini_havuz.py
"""

import json
import sys
from getpass import getpass
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
CONFIG_PATH = BASE_DIR / "config" / "api_keys.json"
sys.path.insert(0, str(BASE_DIR))


def load_config() -> dict:
    try:
        return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"config/api_keys.json okunamadi: {e}")
        raise SystemExit(1)


def save_config(config: dict) -> None:
    CONFIG_PATH.write_text(json.dumps(config, indent=2, ensure_ascii=False), encoding="utf-8")


def current_keys(config: dict) -> list[str]:
    keys = []
    single = config.get("gemini_api_key")
    if isinstance(single, str) and single.strip():
        keys.append(single.strip())
    pool = config.get("gemini_api_keys")
    if isinstance(pool, list):
        keys += [k.strip() for k in pool if isinstance(k, str) and k.strip()]
    return keys


def test_key(key: str) -> tuple[bool, str]:
    """Returns (works, message). A key over quota is still ACCEPTED — it is a
    valid key that will simply be skipped until its quota resets, which is the
    normal state for a spare key. Only a rejected/invalid key is refused."""
    try:
        from google import genai
        client = genai.Client(api_key=key)
        client.models.generate_content(model="gemini-flash-latest", contents="hi")
        return True, "calisiyor"
    except Exception as e:
        text = str(e)
        if any(m in text for m in ("429", "RESOURCE_EXHAUSTED", "quota")):
            return True, "gecerli ama bugunku kotasi dolu (havuza eklendi)"
        if "API key not valid" in text or "API_KEY_INVALID" in text or "400" in text:
            return False, "GECERSIZ anahtar"
        return False, f"test edilemedi: {text[:90]}"


def main() -> None:
    config = load_config()
    existing = current_keys(config)

    print("\n" + "=" * 58)
    print("  GEMINI ANAHTAR HAVUZU")
    print("=" * 58)
    print(f"\nSu an havuzda {len(existing)} anahtar var.")
    print("\nHer anahtar FARKLI bir Google hesabindan olmali —")
    print("ayni hesaptan alinanlar ayni kotayi paylasir, havuz ise yaramaz.")
    print("\nAnahtar almak icin: https://aistudio.google.com/apikey")
    print("\nAnahtarlari tek tek yapistir. Bitirmek icin bos birakip Enter'a bas.")
    print("(Yazarken gorunmeyecek)\n")

    added = 0
    while True:
        value = getpass(f"Anahtar #{len(existing) + added + 1} (bitirmek icin Enter): ").strip()
        if not value:
            break

        if value in existing:
            print("   -> Bu anahtar zaten havuzda, atlandi.\n")
            continue

        print("   -> test ediliyor...", end=" ", flush=True)
        works, message = test_key(value)
        print(message)

        if not works:
            print("   -> EKLENMEDI. Anahtari kontrol edip tekrar dene.\n")
            continue

        if not config.get("gemini_api_key"):
            config["gemini_api_key"] = value
        else:
            pool = config.get("gemini_api_keys")
            pool = pool if isinstance(pool, list) else []
            pool.append(value)
            config["gemini_api_keys"] = pool

        save_config(config)
        existing.append(value)
        added += 1
        print(f"   -> EKLENDI. Havuzda toplam {len(existing)} anahtar.\n")

    print("=" * 58)
    if added:
        print(f"{added} yeni anahtar eklendi. Havuzda toplam {len(existing)} anahtar.")
        print("Biri gunluk kotasini doldurdugunda otomatik olarak digerine gecilecek.")
        print("\nDegisikligin gecerli olmasi icin JARVIS'i yeniden baslat.")
    else:
        print(f"Yeni anahtar eklenmedi. Havuzda {len(existing)} anahtar var.")
    print("=" * 58 + "\n")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nIptal edildi.")
