"""
market_watch — JARVIS'ten BAĞIMSIZ çalışan piyasa/finans izleme paketi.

Değerli maden, döviz ve kripto fiyatlarını + TL'yi etkileyebilecek finans
haberlerini periyodik olarak toplar, JARVIS/memory/market_briefing.json'a
yazar (JARVIS'in ana ekranı bunu okur) ve ayrı, özel bir Telegram botuna
push bildirimi gönderir. Kendi süreci olarak çalışır (bkz. monitor.py,
watchdog_market_bot.vbs) — JARVIS'in asyncio çekirdeğine hiç dokunmaz.
"""
