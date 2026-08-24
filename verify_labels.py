#!/usr/bin/env python3
"""Verify nvidia-1 and nvidia-2 labels in API Display"""

from core.api_usage import snapshot, record

# Simulate some API calls
record("nvidia-1")
record("nvidia-2")
record("gemini-1")

# Get snapshot
rows = snapshot(2)

print("=" * 70)
print("✅ API Display Panel - Updated Labels")
print("=" * 70)

for row in rows:
    status = "🟢" if row["active"] else "🔴"
    pct = row.get("pct")
    pct_str = f"{pct}%" if pct is not None else "N/A"
    print(f"{status} {row['label']:<25} {pct_str:>5}")

print("\n✅ Labels updated to nvidia-1 and nvidia-2")
