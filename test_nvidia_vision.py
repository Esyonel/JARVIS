#!/usr/bin/env python3
"""Test NVIDIA Vision API Integration"""

import json
from pathlib import Path
from plugins.nvidia_vision_api import run

# Load API keys from config
config_path = Path("config/api_keys.json")
with open(config_path) as f:
    config = json.load(f)

vision_api_key = config.get("nvidia_vision_api_key")

if not vision_api_key:
    print("❌ Error: nvidia_vision_api_key not found in config/api_keys.json")
    exit(1)

print("=" * 70)
print("🖼️  NVIDIA Vision API Plugin Test")
print("=" * 70)

# Test: Analyze NVIDIA example image
print("\n📝 Test: Analyzing NVIDIA example image")
print("-" * 70)

result = run({
    "api_key": vision_api_key,
    "image_url": "https://assets.ngc.nvidia.com/products/api-catalog/phi-3-5-vision/example1b.jpg",
    "question": "What is in this image? Describe what you see.",
    "model": "google/gemma-4-31b-it",
    "enable_thinking": True,
    "max_tokens": 2048
})

print(f"🎨 Vision Analysis:\n{result}")

# Test API display
print("\n" + "=" * 70)
print("📊 API Display Panel")
print("=" * 70)

from core.api_usage import snapshot

rows = snapshot(4)

for row in rows:
    status = "🟢" if row["active"] else "🔴"
    pct = row.get("pct")
    pct_str = f"{pct}%" if pct is not None else "N/A"
    print(f"{status} {row['label']:<25} {pct_str:>5}")

print("\n" + "=" * 70)
print("✅ nvidia_vision now appears in API Display Panel!")
print("=" * 70)
