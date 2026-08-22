import json
import os
from datetime import datetime, timedelta

CALENDAR_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "memory", "calendar.json")

PLUGIN = {
    "name": "calendar_manager",
    "description": "Takvime etkinlik veya randevu ekler, mevcut etkinlikleri listeler veya siler. Tarih ve saat bazlı ajanda yönetimi sağlar.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "description": "Yapılacak işlem: 'add' (etkinlik ekle), 'list' (etkinlikleri listele), 'delete' (etkinlik sil), 'clear' (tümünü temizle)."
            },
            "title": {
                "type": "STRING",
                "description": "Etkinlik veya randevu başlığı / açıklaması."
            },
            "date": {
                "type": "STRING",
                "description": "Tarih (YYYY-AA-GG formatında veya 'bugun', 'yarin' gibi). Boş bırakılırsa bugün kabul edilir."
            },
            "time": {
                "type": "STRING",
                "description": "Saat (SS:DD formatında, örn: 14:30)."
            }
        },
        "required": ["action"]
    }
}

def _load_calendar() -> list:
    if not os.path.exists(CALENDAR_FILE):
        return []
    try:
        with open(CALENDAR_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []

def _save_calendar(events: list) -> None:
    os.makedirs(os.path.dirname(CALENDAR_FILE), exist_ok=True)
    with open(CALENDAR_FILE, "w", encoding="utf-8") as f:
        json.dump(events, f, ensure_ascii=False, indent=2)

def _parse_date(date_str: str) -> str:
    if not date_str:
        return datetime.now().strftime("%Y-%m-%d")
    d_str = date_str.strip().lower()
    if d_str in ["bugun", "bugün", "today"]:
        return datetime.now().strftime("%Y-%m-%d")
    elif d_str in ["yarin", "yarın", "tomorrow"]:
        return (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
    try:
        parsed = datetime.strptime(date_str.strip(), "%Y-%m-%d")
        return parsed.strftime("%Y-%m-%d")
    except Exception:
        return datetime.now().strftime("%Y-%m-%d")

def run(parameters: dict, player=None, session_memory=None) -> str:
    try:
        action = parameters.get("action", "list").lower().strip()
        title = parameters.get("title", "").strip()
        raw_date = parameters.get("date", "")
        time_val = parameters.get("time", "").strip()

        events = _load_calendar()

        if action == "add":
            if not title:
                return "Etkinlik eklemek için bir başlık belirtmelisiniz."
            date_val = _parse_date(raw_date)
            new_event = {
                "id": len(events) + 1,
                "title": title,
                "date": date_val,
                "time": time_val if time_val else "Belirtilmedi",
                "created_at": datetime.now().isoformat()
            }
            events.append(new_event)
            _save_calendar(events)
            time_info = f" saat {time_val}" if time_val else ""
            return f"{date_val}{time_info} için '{title}' takvime eklendi."

        elif action == "list":
            if not events:
                return "Takviminizde kayıtlı herhangi bir etkinlik bulunmuyor."
            
            filter_date = _parse_date(raw_date) if raw_date else None
            if filter_date:
                filtered = [e for e in events if e.get("date") == filter_date]
                if not filtered:
                    return f"{filter_date} tarihi için planlanmış bir etkinlik yok."
                items = [f"{e.get('title')} ({e.get('time', '')})" for e in filtered]
                return f"{filter_date} tarihindeki etkinlikleriniz: " + ", ".join(items) + "."
            else:
                events.sort(key=lambda x: (x.get("date", ""), x.get("time", "")))
                upcoming = [f"{e.get('date')} {e.get('time', '')}: {e.get('title')}" for e in events[:5]]
                return "Yaklaşan etkinlikleriniz: " + "; ".join(upcoming) + "."

        elif action == "delete":
            if not title:
                return "Silinecek etkinliğin adını belirtmelisiniz."
            initial_count = len(events)
            events = [e for e in events if title.lower() not in e.get("title", "").lower()]
            if len(events) < initial_count:
                _save_calendar(events)
                return f"'{title}' içeren etkinlikler takvimden silindi."
            return f"'{title}' ile eşleşen bir etkinlik bulunamadı."

        elif action == "clear":
            _save_calendar([])
            return "Tüm takvim etkinlikleri temizlendi."

        else:
            return f"Geçersiz takvim işlemi: {action}."

    except Exception as e:
        return f"Takvim işlemi sırasında bir hata oluştu: {str(e)}"
