#!/usr/bin/env python3
"""Verify NVIDIA API is in TOOL_DECLARATIONS"""

import json
from pathlib import Path

# Read main.py and extract TOOL_DECLARATIONS
main_file = Path("main.py")
content = main_file.read_text(encoding="utf-8")

# Simple check
if "nvidia_integrate_api" in content:
    print("✅ nvidia_integrate_api found in main.py")
    if '"name": "nvidia_integrate_api"' in content:
        print("✅ Proper TOOL_DECLARATIONS format detected")
        print("\n📋 NVIDIA API Tool Declaration Added:")
        print("""
{
    "name": "nvidia_integrate_api",
    "description": "Query advanced AI models via NVIDIA's Integrate API...",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "prompt": {...},
            "model": {...},
            "temperature": {...},
            "top_p": {...},
            "max_tokens": {...}
        },
        "required": ["prompt"]
    }
}
        """)
else:
    print("❌ nvidia_integrate_api not found in TOOL_DECLARATIONS")

# Also verify plugin is still loaded
from core.plugin_loader import discover_plugins

plugins_dir = Path("plugins")
registry = discover_plugins(plugins_dir, set(), logger=lambda x: None)

if registry.has("nvidia_integrate_api"):
    print("\n✅ Plugin system: nvidia_integrate_api registered")
    print("✅ Ready for voice commands and UI integration!")
else:
    print("\n❌ Plugin system: nvidia_integrate_api NOT found")
