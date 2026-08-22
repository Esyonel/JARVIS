"""
Adds a fallback AI provider key to config/api_keys.json.

Run this yourself and paste the key at the prompt — the key goes straight
from your terminal into the local config file. Nothing is printed back and
nothing is sent anywhere.

Usage:  .venv\\Scripts\\python.exe add_provider_key.py
"""

import json
from getpass import getpass
from pathlib import Path

CONFIG_PATH = Path(__file__).resolve().parent / "config" / "api_keys.json"

PROVIDERS = {
    "1": ("openrouter_api_key", "OpenRouter  (https://openrouter.ai/keys)"),
    "2": ("groq_api_key",       "Groq        (https://console.groq.com/keys)"),
    "3": ("cerebras_api_key",   "Cerebras    (https://cloud.cerebras.ai)"),
    "4": ("gemini_api_key",     "Gemini — SES icin gerekli  (https://aistudio.google.com/apikey)"),
}


def main() -> None:
    print("\nHangi saglayicinin anahtarini eklemek istiyorsun?\n")
    for num, (_key, label) in PROVIDERS.items():
        print(f"  {num}) {label}")

    choice = input("\nSecim (1-4): ").strip()
    if choice not in PROVIDERS:
        print("Gecersiz secim, iptal edildi.")
        return

    key_name, label = PROVIDERS[choice]
    print(f"\n{label} anahtarini yapistir (yazarken gorunmeyecek):")
    value = getpass("Anahtar: ").strip()

    if not value:
        print("Bos anahtar, iptal edildi.")
        return

    try:
        config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"config/api_keys.json okunamadi: {e}")
        return

    config[key_name] = value
    CONFIG_PATH.write_text(json.dumps(config, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"\nTamam — '{key_name}' kaydedildi ({len(value)} karakter).")
    print("Gemini kotasi bittiginde JARVIS otomatik olarak bu saglayiciya gececek.")
    print("\nDogrulamak icin:")
    print("  .venv\\Scripts\\python.exe -c \"import sys; sys.path.insert(0,'.'); "
          "from core.ai_text import available_providers; print(available_providers())\"")


if __name__ == "__main__":
    main()
