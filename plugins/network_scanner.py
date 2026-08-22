"""Yerel agdaki aktif cihazlari ve ARP tablosunu tarayan JARVIS eklentisi."""

import re
import subprocess
import platform

PLUGIN = {
    "name": "scan_local_network",
    "description": "Yerel ağdaki aktif cihazları ARP tablosundan tarar; IP, MAC adresi ve üretici bilgilerini Türkçe özet olarak bildirir.",
    "parameters": {
        "type": "OBJECT",
        "properties": {},
        "required": []
    }
}

# Yaygın OUI (MAC adresi ilk 3 bayt) üretici eşleştirmeleri
OUI_VENDORS = {
    "00:1A:11": "Google",
    "F4:F5:DB": "Google",
    "08:00:27": "VirtualBox",
    "00:0C:29": "VMware",
    "00:50:56": "VMware",
    "B8:27:EB": "Raspberry Pi",
    "DC:A6:32": "Raspberry Pi",
    "E4:5F:01": "Raspberry Pi",
    "28:CD:C1": "Apple",
    "3C:06:30": "Apple",
    "AC:BC:32": "Apple",
    "F0:18:98": "Apple",
    "BC:D1:D3": "Apple",
    "A4:83:E7": "Apple",
    "14:7D:DA": "Apple",
    "F8:FF:C2": "Apple",
    "50:DE:06": "Samsung",
    "84:25:19": "Samsung",
    "94:01:C2": "Samsung",
    "CC:07:AB": "Samsung",
    "64:89:9A": "Xiaomi",
    "78:11:DC": "Xiaomi",
    "50:EC:50": "TP-Link",
    "60:32:B1": "TP-Link",
    "98:48:27": "TP-Link",
    "F4:EC:38": "TP-Link",
    "D8:07:B6": "Huawei",
    "00:1E:10": "Huawei",
    "70:8A:09": "Huawei",
    "AC:72:89": "Intel",
    "68:05:71": "Intel",
    "00:1B:21": "Intel",
    "04:D4:C4": "ASUS",
    "70:4D:7B": "ASUS",
    "2C:FD:A1": "Amazon",
    "44:65:0D": "Amazon",
    "FC:A6:67": "Amazon",
    "A4:CF:12": "Espressif (IoT/ESP)",
    "24:0A:C4": "Espressif (IoT/ESP)",
    "30:AE:A4": "Espressif (IoT/ESP)",
    "84:F3:EB": "Espressif (IoT/ESP)",
    "00:15:5D": "Microsoft",
    "70:85:C2": "Dell",
    "18:03:73": "Dell",
    "3C:D9:2B": "HP",
    "A0:D3:C1": "LG Electronics",
    "FC:F1:36": "Sony",
    "00:26:86": "Cisco",
    "00:E0:4C": "Realtek"
}

def _get_vendor(mac: str) -> str:
    formatted_mac = mac.upper().replace("-", ":")
    prefix = ":".join(formatted_mac.split(":")[:3])
    return OUI_VENDORS.get(prefix, "Bilinmeyen Cihaz / Uretici")

def _is_broadcast_or_multicast(ip: str, mac: str) -> bool:
    if ip.startswith("224.") or ip.startswith("239.") or ip.endswith(".255") or ip == "255.255.255.255":
        return True
    mac_norm = mac.lower().replace("-", ":")
    if mac_norm in ("ff:ff:ff:ff:ff:ff", "00:00:00:00:00:00") or mac_norm.startswith("01:00:5e"):
        return True
    return False

def run(parameters: dict, player=None, session_memory=None) -> str:
    try:
        system = platform.system().lower()
        cmd = ["arp", "-a"]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        output = result.stdout

        devices = []
        seen_ips = set()

        # Regex matches for IP and MAC address pairs across Windows, Linux and macOS
        # Example Windows: 192.168.1.1  a0-b1-c2-d3-e4-f5  dynamic
        # Example Unix: ? (192.168.1.1) at a0:b1:c2:d3:e4:f5 on eth0
        ip_mac_pattern = re.compile(
            r'(?:\()?(\d{1,3}(?:\.\d{1,3}){3})(?:\))?\s+(?:at\s+)?([0-9a-fA-F]{1,2}(?:[:-][0-9a-fA-F]{1,2}){5})'
        )

        for line in output.splitlines():
            match = ip_mac_pattern.search(line)
            if match:
                ip, mac = match.groups()
                mac = mac.replace("-", ":").upper()
                # MAC adresini standart formata (00:11:22:33:44:55) donustur
                mac_parts = [p.zfill(2) for p in mac.split(":")]
                formatted_mac = ":".join(mac_parts)

                if ip not in seen_ips and not _is_broadcast_or_multicast(ip, formatted_mac):
                    seen_ips.add(ip)
                    vendor = _get_vendor(formatted_mac)
                    devices.append({"ip": ip, "mac": formatted_mac, "vendor": vendor})

        if not devices:
            return "Yerel ağda aktif cihaz bulunamadı veya ARP tablosu boş."

        lines = [f"Yerel ağda {len(devices)} aktif cihaz tespit edildi:"]
        for idx, dev in enumerate(devices, 1):
            lines.append(f"{idx}. IP: {dev['ip']} - MAC: {dev['mac']} ({dev['vendor']})")

        return "\n".join(lines)

    except subprocess.TimeoutExpired:
        return "Ağ tarama işlemi zaman aşımına uğradı."
    except Exception as e:
        return f"Ağ taraması sırasında hata oluştu: {str(e)}"
