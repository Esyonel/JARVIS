"""
plugins/task_master.py — local to-do list.

calendar_manager.py already covers dated events/appointments; this covers
undated action items. No Notion/Trello OAuth app exists anywhere in this
codebase, so — like calendar_manager.py — it's real local JSON storage
rather than a fake remote API call.
"""
import json
from datetime import datetime
from pathlib import Path

_BASE = Path(__file__).resolve().parent.parent / "memory"
_FILE = _BASE / "tasks.json"

PLUGIN = {
    "name": "task_master",
    "description": (
        "Yapılacaklar listesini yönetir: görev oluşturur, bekleyenleri listeler, "
        "tamamlandı olarak işaretler veya siler. Tarihsiz görevler içindir — "
        "tarihli randevular için calendar_manager kullanılır. 'yeni görev ekle', "
        "'bekleyen görevlerim ne' gibi komutlarda kullanılır."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "description": "'create', 'list', 'complete', 'delete'."
            },
            "title": {"type": "STRING", "description": "Görev başlığı."},
            "priority": {"type": "STRING", "description": "'Düşük', 'Normal' veya 'Yüksek'. Varsayılan 'Normal'."},
            "task_id": {"type": "NUMBER", "description": "'complete'/'delete' için görev numarası."}
        },
        "required": ["action"]
    }
}


def _load() -> list:
    if not _FILE.exists():
        return []
    try:
        return json.loads(_FILE.read_text(encoding="utf-8"))
    except Exception:
        return []


def _save(tasks: list) -> None:
    _BASE.mkdir(parents=True, exist_ok=True)
    _FILE.write_text(json.dumps(tasks, ensure_ascii=False, indent=2), encoding="utf-8")


def run(parameters: dict, player=None, session_memory=None) -> str:
    action = str(parameters.get("action", "list")).strip().lower()
    tasks = _load()

    if action == "create":
        title = str(parameters.get("title", "")).strip()
        if not title:
            return "Görev başlığı belirtmelisiniz."
        priority = str(parameters.get("priority", "Normal")).strip() or "Normal"
        next_id = max((t["id"] for t in tasks), default=0) + 1
        tasks.append({
            "id": next_id, "title": title, "priority": priority,
            "done": False, "created_at": datetime.now().isoformat(),
        })
        _save(tasks)
        return f"Görev oluşturuldu (#{next_id}): {title} — {priority} öncelik."

    elif action == "list":
        pending = [t for t in tasks if not t.get("done")]
        if not pending:
            return "Bekleyen görev yok."
        items = [f"#{t['id']} {t['title']} ({t.get('priority', 'Normal')})" for t in pending]
        return "Bekleyen görevler: " + "; ".join(items) + "."

    elif action == "complete":
        try:
            tid = int(parameters.get("task_id"))
        except (TypeError, ValueError):
            return "Geçerli bir görev numarası belirtmelisiniz."
        for t in tasks:
            if t["id"] == tid:
                t["done"] = True
                _save(tasks)
                return f"#{tid} görevi tamamlandı olarak işaretlendi."
        return f"#{tid} numaralı görev bulunamadı."

    elif action == "delete":
        try:
            tid = int(parameters.get("task_id"))
        except (TypeError, ValueError):
            return "Geçerli bir görev numarası belirtmelisiniz."
        before = len(tasks)
        tasks = [t for t in tasks if t["id"] != tid]
        if len(tasks) < before:
            _save(tasks)
            return f"#{tid} görevi silindi."
        return f"#{tid} numaralı görev bulunamadı."

    return f"Bilinmeyen eylem: {action}"
