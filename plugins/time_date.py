from datetime import datetime

PLUGIN = {
    "name": "get_current_time_date",
    "description": "Şu anki saati ve tarihi Türkçe olarak döndürür.",
    "parameters": {
        "type": "OBJECT",
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


def run(parameters: dict, player=None, session_memory=None) -> str:
    try:
        now = datetime.now()
        day_name = DAYS_TR[now.weekday()]
        month_name = MONTHS_TR[now.month - 1]
        time_str = now.strftime("%H:%M")
        return f"Bugün {now.day} {month_name} {now.year}, {day_name}. Saat {time_str}."
    except Exception as e:
        return f"Saat ve tarih bilgisi alınamadı: {str(e)}"
