"""Current time and date plugin for JARVIS."""

from datetime import datetime

PLUGIN = {
    "name": "get_current_time_date",
    "description": "Şu anki saat ve tarih bilgisini Türkçe olarak döner.",
    "parameters": {
        "type": "object",
        "properties": {},
        "required": [],
    },
}

MONTHS_TR = [
    "Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran",
    "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık"
]

DAYS_TR = [
    "Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar"
]


def run(parameters=None, player=None, session_memory=None):
    try:
        now = datetime.now()
        day_name = DAYS_TR[now.weekday()]
        month_name = MONTHS_TR[now.month - 1]
        formatted = f"Bugün {now.day} {month_name} {now.year} {day_name}, saat {now.strftime('%H:%M')}."
        return {
            "status": "success",
            "time": now.strftime("%H:%M"),
            "date": f"{now.day} {month_name} {now.year}",
            "day": day_name,
            "message": formatted,
        }
    except Exception as e:
        return {"status": "error", "message": f"Saat/tarih alınırken bir hata oluştu: {e}"}
