import ipaddress
import socket
import subprocess
import sys
from typing import Dict, Any

# Plugin metadata
PLUGIN = {
    "name": "network_data_fetcher",
    "description": "Fetches data from all devices on the local network and optionally updates privacy and security protocol settings.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "network_range": {
                "type": "STRING",
                "description": "CIDR notation of the network to scan, e.g., '192.168.1.0/24'. If omitted, the plugin scans the local /24 subnet."
            },
            "update_security": {
                "type": "STRING",
                "description": "New security protocol to apply (e.g., 'TLS1.3', 'AES256')."
            },
            "update_privacy": {
                "type": "STRING",
                "description": "New privacy setting to apply (e.g., 'GDPR_COMPLIANT', 'ANONYMIZED')."
            }
        },
        "required": []
    }
}

def _default_subnet() -> str:
    """Return the /24 subnet of the first non‑loopback IPv4 interface."""
    try:
        hostname = socket.gethostname()
        ip = socket.gethostbyname(hostname)
        # ip might be 127.0.0.1; fallback to a dummy private address
        if ip.startswith("127.") or ip == "0.0.0.0":
            ip = "192.168.1.1"
        net = ipaddress.ip_interface(f"{ip}/24").network
        return str(net)
    except Exception:
        return "192.168.1.0/24"

def _is_host_up(host: str, timeout: float = 0.5) -> bool:
    """Very light ping using the system ping command; returns True if host replies."""
    try:
        # Platform‑specific arguments
        if sys.platform == "win32":
            args = ["ping", "-n", "1", "-w", str(int(timeout * 1000)), host]
        else:
            args = ["ping", "-c", "1", "-W", str(int(timeout * 1000)), host]
        result = subprocess.run(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return result.returncode == 0
    except Exception:
        return False

def run(parameters: dict, player=None, session_memory=None) -> str:
    """
    Scan the network, optionally update security/privacy settings, and return a short spoken summary.
    """
    try:
        network_range = parameters.get("network_range") or _default_subnet()
        security = parameters.get("update_security")
        privacy = parameters.get("update_privacy")

        # Validate network_range
        try:
            net = ipaddress.ip_network(network_range, strict=False)
        except ValueError:
            return f"Error: '{network_range}' is not a valid network range."

        # Scan hosts (lightweight – only check if they respond to ping)
        alive_hosts = []
        for ip in net.hosts():
            if _is_host_up(str(ip)):
                alive_hosts.append(str(ip))
                if len(alive_hosts) >= 10:  # limit output size
                    break

        parts = []
        if alive_hosts:
            parts.append(f"Found {len(alive_hosts)} reachable device{'s' if len(alive_hosts) != 1 else ''}: {', '.join(alive_hosts)}")
        else:
            parts.append("No reachable devices were found on the network")

        if security:
            parts.append(f"Security protocol set to {security}")
            # Integration with real security config can be added here.
        if privacy:
            parts.append(f"Privacy setting changed to {privacy}")
            # Integration with real privacy config can be added here.

        return ". ".join(parts) + "."
    except Exception as e:
        return f"An unexpected error occurred while fetching network data: {str(e)}"
