"""
Plugin to test internet speed and report the results in Turkish.
"""

import traceback

try:
    import speedtest
except Exception:
    speedtest = None

PLUGIN = {
    "name": "internet_speed_test",
    "description": "Kullanıcının internet bağlantı hızını ölçer ve indirgeme ve yükleme hızlarını Türkçe olarak raporlar.",
    "parameters": {
        "type": "OBJECT",
        "properties": {},
        "required": []
    }
}

def run(parameters: dict, player=None, session_memory=None) -> str:
    """Measure internet download and upload speed.

    Returns a short Turkish sentence with the results.
    """
    if speedtest is None:
        return "İnternet hızı ölçmek için gerekli kütüphane bulunamadı."
    try:
        st = speedtest.Speedtest()
        st.get_best_server()
        download_bps = st.download()
        upload_bps = st.upload()
        # Convert bits per second to megabits per second
        download_mbps = download_bps / 1_000_000
        upload_mbps = upload_bps / 1_000_000
        # Round to one decimal place for readability
        download_str = f"{download_mbps:.1f}"
        upload_str = f"{upload_mbps:.1f}"
        return f"İndirme hızı: {download_str} Mbps, yükleme hızı: {upload_str} Mbps."
    except Exception:
        # Optionally log the traceback if a logger is available
        return "İnternet hızı ölçülürken bir hata oluştu."
