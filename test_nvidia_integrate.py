#!/usr/bin/env python3
"""Test script for NVIDIA Integrate API plugin"""

import json
from pathlib import Path
from plugins.nvidia_integrate_api import run

# Load API key from config
config_path = Path("config/api_keys.json")
with open(config_path) as f:
    config = json.load(f)

api_key = config.get("nvidia_integrate_api_key")

if not api_key:
    print("❌ Error: nvidia_integrate_api_key not found in config/api_keys.json")
    exit(1)

print("=" * 60)
print("🧪 NVIDIA Integrate API Plugin Test")
print("=" * 60)

# Test 1: Simple question
print("\n📝 Test 1: Simple Math Question")
print("-" * 60)
result = run({
    "api_key": api_key,
    "prompt": "Which number is larger, 9.11 or 9.8?",
    "model": "minimaxai/minimax-m3"
})
print(f"Response: {result}")

# Test 2: Turkish question
print("\n📝 Test 2: Turkish Question")
print("-" * 60)
result = run({
    "api_key": api_key,
    "prompt": "Merhaba! Bana kısaca kendinden bahset.",
    "temperature": 0.7,
    "max_tokens": 200
})
print(f"Response: {result}")

# Test 3: Creative task
print("\n📝 Test 3: Creative Task")
print("-" * 60)
result = run({
    "api_key": api_key,
    "prompt": "Write a short funny haiku about programming.",
    "temperature": 1.5
})
print(f"Response: {result}")

print("\n" + "=" * 60)
print("✅ All tests completed!")
print("=" * 60)
