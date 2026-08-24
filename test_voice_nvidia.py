#!/usr/bin/env python3
"""Test NVIDIA Integrate API with voice command simulation"""

import json
from pathlib import Path
from core.plugin_loader import discover_plugins

# Discover all plugins
plugins_dir = Path("plugins")
registry = discover_plugins(plugins_dir, set())

# List all loaded plugins
print("\n" + "=" * 60)
print("🔍 JARVIS Plugin Registry")
print("=" * 60)

all_plugins = registry.list_for_ui()
for plugin in all_plugins:
    status = "✅" if plugin["valid"] else "❌"
    enabled = "🟢" if plugin["enabled"] else "🔴" if plugin["valid"] else "⚠️"
    print(f"{status} {enabled} {plugin['name']:<30} ({plugin['file']})")
    if plugin["error"]:
        print(f"     ⚠️  {plugin['error']}")

# Check if nvidia_integrate_api is loaded
print("\n" + "=" * 60)
print("🤖 NVIDIA Plugin Status")
print("=" * 60)

if registry.has("nvidia_integrate_api"):
    print("✅ nvidia_integrate_api plugin loaded successfully!")
    
    # Load API key
    config_path = Path("config/api_keys.json")
    with open(config_path) as f:
        config = json.load(f)
    api_key = config.get("nvidia_integrate_api_key")
    
    # Simulate voice command
    print("\n📝 Simulating voice command: 'Ask NVIDIA a question'")
    print("-" * 60)
    
    result = registry.run("nvidia_integrate_api", {
        "api_key": api_key,
        "prompt": "Türkçe kullanarak kısa bir şiir yaz.",
        "model": "minimaxai/minimax-m3",
        "temperature": 1.2,
        "max_tokens": 256
    })
    
    print(f"\n🎤 JARVIS Response:\n{result}")
else:
    print("❌ nvidia_integrate_api plugin NOT found!")
    print("\nAvailable plugins with 'nvidia':")
    for plugin in all_plugins:
        if "nvidia" in plugin["name"].lower():
            print(f"  - {plugin['name']}")

print("\n" + "=" * 60)
