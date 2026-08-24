#!/usr/bin/env python3
"""Test API Display Panel with NVIDIA API"""

from core.api_usage import snapshot, record, remaining_pct

# Simulate API calls
record("gemini-1")
record("gemini-2")
record("openrouter")
record("groq")
record("cerebras")
record("nvidia_integrate")  # Test NVIDIA
record("nvidia_integrate")

# Get snapshot with 4 Gemini keys
rows = snapshot(4)

print("=" * 60)
print("📊 API Display Panel")
print("=" * 60)

for row in rows:
    status = "🟢" if row["active"] else "🔴"
    pct = row.get("pct")
    pct_str = f"{pct}%" if pct is not None else "N/A"
    print(f"{status} {row['label']:<25} {pct_str:>5}")

print("\n" + "=" * 60)
print("✅ nvidia_integrate now appears in API Display Panel!")
print("=" * 60)

# Verify remaining_pct
print("\n📈 Remaining Percentages:")
for api in ["gemini-1", "openrouter", "groq", "cerebras", "nvidia_integrate"]:
    pct = remaining_pct(api)
    print(f"  {api:<25} {pct}%" if pct else f"  {api:<25} N/A")
