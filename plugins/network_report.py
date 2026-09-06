import os
import socket
import psutil
import matplotlib.pyplot as plt
from datetime import datetime

# Plugin metadata required by JARVIS
PLUGIN = {
    "name": "network_report",
    "description": "Bilgisayarınızdaki aktif ağ bağlantılarını ve dinlenen TCP/UDP portlarını tarayarak süreç, protokol ve açık port bilgilerini özetleyen bir görsel rapor (PNG) oluşturur.",
    "parameters": {
        "type": "OBJECT",
        "properties": {},
        "required": []
    }
}


def _protocol_name(conn_type: int) -> str:
    """Map socket type to protocol name."""
    if conn_type == socket.SOCK_STREAM:
        return "TCP"
    if conn_type == socket.SOCK_DGRAM:
        return "UDP"
    return "OTHER"


def _gather_connections():
    """Collect network connection information using psutil.

    Returns a list of dicts with keys: pid, process, protocol, laddr, raddr, status.
    """
    connections = []
    for conn in psutil.net_connections(kind="inet"):
        try:
            pid = conn.pid or 0
            proc_name = psutil.Process(pid).name() if pid else "-"
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            proc_name = "-"
        protocol = _protocol_name(conn.type)
        laddr = f"{conn.laddr.ip}:{conn.laddr.port}" if conn.laddr else "-"
        raddr = f"{conn.raddr.ip}:{conn.raddr.port}" if conn.raddr else "-"
        status = conn.status
        connections.append(
            {
                "PID": pid,
                "Process": proc_name,
                "Protocol": protocol,
                "Local Address": laddr,
                "Remote Address": raddr,
                "Status": status,
            }
        )
    return connections


def _create_report_image(data, output_path):
    """Create a PNG image containing a table of the network data.

    Args:
        data (list[dict]): List of connection dictionaries.
        output_path (str): Where to save the PNG.
    """
    # Ensure output directory exists
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    # Sort for readability
    data_sorted = sorted(data, key=lambda x: (x["Protocol"], x["PID"]))
    headers = ["PID", "Process", "Protocol", "Local Address", "Remote Address", "Status"]
    cell_text = [[
        str(item[h]) for h in headers
    ] for item in data_sorted]

    fig, ax = plt.subplots(figsize=(12, max(2, len(cell_text) * 0.25)))
    ax.axis('tight')
    ax.axis('off')
    table = ax.table(cellText=cell_text, colLabels=headers, loc='center', cellLoc='center')
    table.auto_set_font_size(False)
    table.set_fontsize(8)
    table.scale(1, 1.2)

    title = f"Network Connections Report - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    plt.title(title, fontsize=10, pad=12)
    plt.savefig(output_path, bbox_inches='tight', dpi=200)
    plt.close(fig)


def run(parameters: dict, player=None, session_memory=None) -> str:
    """Generate a visual network report and return a short spoken summary.

    The function never raises; any exception is caught and an error message is
    returned so that JARVIS can speak it.
    """
    try:
        connections = _gather_connections()
        if not connections:
            return "Şu anda aktif bir ağ bağlantısı bulunamadı."
        # Define output path inside a dedicated reports folder
        output_path = os.path.join("reports", "network_report.png")
        _create_report_image(connections, output_path)
        return f"Ağ raporu oluşturuldu ve {output_path} dosyasına kaydedildi."
    except Exception as e:
        # Log could be added here; for now we just return a user‑friendly message
        return f"Ağ raporu oluşturulurken bir hata meydana geldi: {str(e)}"
