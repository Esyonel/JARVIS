import os
import shutil

PLUGIN = {
    "name": "disk_usage",
    "description": "Bilgisayarın disk doluluk oranını ve boş alan miktarını Türkçe olarak öğrenir.",
    "parameters": {
        "type": "OBJECT",
        "properties": {},
        "required": []
    }
}

def run(parameters: dict, player=None, session_memory=None) -> str:
    try:
        root_path = os.path.abspath(os.sep)
        total, used, free = shutil.disk_usage(root_path)
        
        used_percent = round((used / total) * 100, 1)
        free_gb = round(free / (1024 ** 3), 1)
        total_gb = round(total / (1024 ** 3), 1)
        
        return f"Ana diskinizin doluluk oranı yüzde {used_percent}. Toplam {total_gb} gigabayt alanın {free_gb} gigabaytı kullanılabilir durumda."
    except Exception as e:
        return f"Disk bilgisi alınırken bir hata oluştu: {e}"
