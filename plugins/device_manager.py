"""
JARVIS plugin — hardware inventory and new-device detection.

Answers "what is connected to my computer" for printers, monitors, Bluetooth
devices, audio devices and USB/phone connections, and — by keeping a snapshot
between runs — reports what has been ADDED or REMOVED since the last check.

Everything is read-only: it enumerates devices, it never installs, disables or
reconfigures them.

Noise filtering matters here. Windows exposes dozens of internal plumbing
entries (root hubs, host controllers, "Bluetooth LE Generic Attribute Service"
repeated per profile) that are not devices a person owns, so they're filtered
out — otherwise every listing is a wall of driver internals and a genuinely
new device is invisible in it.
"""

import json
import subprocess
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
SNAPSHOT_PATH = BASE_DIR / "memory" / "device_snapshot.json"

PLUGIN = {
    "name": "device_manager",
    "description": (
        "Lists the hardware connected to the computer — printers, monitors/screens, "
        "Bluetooth devices (headphones, mouse), audio devices, and USB/phone "
        "connections — and reports what has been newly connected or removed since "
        "the last check. Use for: 'bilgisayarıma neler bağlı', 'yazıcılarım "
        "neler', 'hangi ekranlar bağlı', 'bluetooth cihazlarım', 'telefonum bağlı "
        "mı', 'yeni bir cihaz eklendi mi', 'kulaklığım bağlı mı'. Read-only — it "
        "reports hardware, it does not install or change anything."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "category": {
                "type": "STRING",
                "description": (
                    "Which devices to report: 'yazici' (printers), 'ekran' (monitors), "
                    "'bluetooth', 'ses' (audio), 'usb' (USB/phone), 'yeni' (only what "
                    "changed since last check), or 'hepsi' (everything — default)."
                ),
            },
        },
        "required": [],
    },
}

_TIMEOUT = 25

# Windows plumbing that is not a device the owner would recognise as theirs.
_NOISE = (
    "genel öznitelik", "generic attribute", "kök hub", "root hub",
    "host controller", "bileşik aygıt", "composite device",
    "usb bileşik", "numaralandırıcı", "enumerator", "ağ geçidi hizmeti",
    # Bluetooth exposes one entry per supported PROFILE (phonebook access,
    # object push, PAN, ...) alongside the device itself — those are
    # capabilities, not things plugged in, so they'd bury the real devices.
    "hizmeti", "service", "profili", "profile", "protocol tdi",
    "avrcp transport", "proxy", "teknolojisi",
)


def run(parameters: dict, player=None, session_memory=None) -> str:
    category = (parameters.get("category") or "hepsi").strip().lower()

    try:
        if category.startswith("yeni") or "değişik" in category or "degisik" in category:
            result = _changes_since_last_check()
        else:
            result = _inventory(category)
    except Exception as e:
        result = f"Efendim, cihaz listesi alınamadı: {e}"

    _log(result, player)
    return result[:3000]


def _ps(script: str) -> list[str]:
    """Run a PowerShell snippet, return its non-empty output lines.

    Device names contain Turkish characters, which PowerShell emits in the
    system codepage (cp1254) unless told otherwise — decoding that as UTF-8
    raises and loses the whole category. The script forces UTF-8 output, and
    errors='replace' keeps one odd byte from throwing away a device list.
    """
    proc = subprocess.run(
        ["powershell", "-NoProfile", "-NonInteractive", "-Command",
         "[Console]::OutputEncoding = [System.Text.Encoding]::UTF8; " + script],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=_TIMEOUT,
    )
    if proc.returncode != 0 and not proc.stdout.strip():
        raise RuntimeError((proc.stderr or "PowerShell failed").strip()[:200])
    return [ln.strip() for ln in proc.stdout.splitlines() if ln.strip()]


def _clean(names: list[str]) -> list[str]:
    seen, out = set(), []
    for name in names:
        low = name.lower()
        if any(noise in low for noise in _NOISE):
            continue
        if name in seen:
            continue
        seen.add(name)
        out.append(name)
    return out


def printers() -> list[str]:
    lines = _ps(
        "Get-CimInstance Win32_Printer | ForEach-Object { "
        "if ($_.Default) { $_.Name + ' (varsayilan)' } else { $_.Name } }"
    )
    return _clean(lines)


def monitors() -> list[str]:
    lines = _ps(
        "Get-CimInstance -Namespace root\\wmi WmiMonitorID -ErrorAction SilentlyContinue | "
        "ForEach-Object { -join ([char[]]($_.UserFriendlyName | Where-Object {$_ -ne 0})) }"
    )
    return _clean(lines)


def bluetooth() -> list[str]:
    lines = _ps(
        "Get-PnpDevice -Class Bluetooth -Status OK -ErrorAction SilentlyContinue | "
        "Select-Object -ExpandProperty FriendlyName"
    )
    return _clean(lines)


def audio() -> list[str]:
    lines = _ps(
        "Get-PnpDevice -Class AudioEndpoint,Media -Status OK -ErrorAction SilentlyContinue | "
        "Select-Object -ExpandProperty FriendlyName"
    )
    return _clean(lines)


def usb_devices() -> list[str]:
    lines = _ps(
        "Get-PnpDevice -Status OK -ErrorAction SilentlyContinue | "
        "Where-Object { $_.Class -in @('WPD','USB','Ports','DiskDrive') } | "
        "Select-Object -ExpandProperty FriendlyName"
    )
    return _clean(lines)


_COLLECTORS = {
    "yazici":    ("Yazıcılar", printers),
    "ekran":     ("Ekranlar", monitors),
    "bluetooth": ("Bluetooth cihazları", bluetooth),
    "ses":       ("Ses cihazları", audio),
    "usb":       ("USB / telefon bağlantıları", usb_devices),
}


def _collect_all() -> dict[str, list[str]]:
    snapshot = {}
    for key, (_label, fn) in _COLLECTORS.items():
        try:
            snapshot[key] = fn()
        except Exception as e:
            print(f"[DeviceManager] {key} okunamadı: {e}")
            snapshot[key] = []
    return snapshot


def _inventory(category: str) -> str:
    if category in _COLLECTORS:
        label, fn = _COLLECTORS[category]
        items = fn()
        if not items:
            return f"{label}: bağlı cihaz bulunamadı."
        return f"{label} ({len(items)}):\n" + "\n".join(f"- {i}" for i in items)

    snapshot = _collect_all()
    parts = []
    for key, (label, _fn) in _COLLECTORS.items():
        items = snapshot.get(key, [])
        if items:
            parts.append(f"{label} ({len(items)}): " + ", ".join(items[:6])
                         + (f" ve {len(items) - 6} tane daha" if len(items) > 6 else ""))
    if not parts:
        return "Efendim, hiçbir cihaz okunamadı."
    return "\n".join(parts)


def _changes_since_last_check() -> str:
    current = _collect_all()

    previous = None
    if SNAPSHOT_PATH.exists():
        try:
            previous = json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))
        except Exception:
            previous = None

    SNAPSHOT_PATH.parent.mkdir(parents=True, exist_ok=True)
    SNAPSHOT_PATH.write_text(json.dumps(current, ensure_ascii=False, indent=2), encoding="utf-8")

    if previous is None:
        total = sum(len(v) for v in current.values())
        return (f"İlk kayıt alındı: {total} cihaz kaydedildi. "
                "Bundan sonra yeni bir cihaz eklendiğinde söyleyebilirim.")

    added, removed = [], []
    for key, (label, _fn) in _COLLECTORS.items():
        now, before = set(current.get(key, [])), set(previous.get(key, []))
        added += [f"{label[:-3] if label.endswith('ları') else label}: {n}" for n in sorted(now - before)]
        removed += [f"{label[:-3] if label.endswith('ları') else label}: {n}" for n in sorted(before - now)]

    if not added and not removed:
        return "Son kontrolden bu yana yeni bir cihaz eklenmemiş veya çıkarılmamış."

    parts = []
    if added:
        parts.append(f"YENİ BAĞLANAN ({len(added)}):\n" + "\n".join(f"+ {a}" for a in added))
    if removed:
        parts.append(f"ÇIKARILAN ({len(removed)}):\n" + "\n".join(f"- {r}" for r in removed))
    return "\n\n".join(parts)


def _log(message: str, player=None) -> None:
    print(f"[DeviceManager] {message[:250]}")
    if player:
        try:
            player.write_log(f"JARVIS: {message}")
        except Exception:
            pass
