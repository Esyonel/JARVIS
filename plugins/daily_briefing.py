"""
Daily briefing plugin — weather + Turkish newspaper headlines + exchange rates
in one spoken summary. Drop-in JARVIS plugin (see _template.py for the format).

Sources:
  - Weather:   wttr.in (no API key, Turkish descriptions via lang=tr)
  - Headlines: Hürriyet / NTV / Sabah RSS feeds (no API key)
  - Exchange:  exchangerate-api.com public endpoint (no API key)

Each section is fetched independently and wrapped in its own try/except, so a
single failing source (feed down, no internet, rate limit) never breaks the
other two — it just reports that one section as unavailable.
"""

import xml.etree.ElementTree as ET
from urllib.parse import quote

import requests

from memory.memory_manager import load_memory

PLUGIN = {
    "name": "daily_briefing",
    "description": (
        "Gives a combined spoken daily briefing: weather, Turkish newspaper "
        "headlines, and USD/EUR-TRY exchange rates. Use this when the user asks "
        "for a summary/briefing of their day, 'bugün ne var', 'günlük özet', "
        "'hava durumu ve haberleri anlat', 'gazete başlıkları neler', 'brifing ver', "
        "or similar — this returns real spoken data, unlike the plain weather tool "
        "which only opens a browser. Can also be asked for just one section "
        "(e.g. only headlines, only weather, only exchange rates) via the "
        "'sections' argument."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "city": {
                "type": "STRING",
                "description": (
                    "City for the weather section (e.g. 'Istanbul', 'Ankara'). "
                    "Optional — if omitted, the city saved in the user's memory "
                    "is used, falling back to Istanbul."
                ),
            },
            "sections": {
                "type": "STRING",
                "description": (
                    "Which parts to include, comma-separated: 'hava' (weather), "
                    "'haberler' (news headlines), 'doviz' (exchange rates), or "
                    "'hepsi' (all — default if omitted)."
                ),
            },
        },
        "required": [],
    },
}

_NEWS_FEEDS = [
    ("Hürriyet", "https://www.hurriyet.com.tr/rss/anasayfa"),
    ("NTV",      "https://www.ntv.com.tr/gundem.rss"),
    ("Sabah",    "https://www.sabah.com.tr/rss/anasayfa.xml"),
]
_HEADERS = {"User-Agent": "Mozilla/5.0 (JARVIS daily_briefing plugin)"}
_TIMEOUT = 8
_HEADLINES_PER_SOURCE = 4


def run(parameters: dict, player=None, session_memory=None) -> str:
    try:
        wanted = (parameters.get("sections") or "hepsi").strip().lower()
        want_weather = "hepsi" in wanted or "hava" in wanted
        want_news    = "hepsi" in wanted or "haber" in wanted or "gazete" in wanted
        want_fx      = "hepsi" in wanted or "doviz" in wanted or "döviz" in wanted or "kur" in wanted
        if not (want_weather or want_news or want_fx):
            want_weather = want_news = want_fx = True

        city = (parameters.get("city") or "").strip() or _default_city()

        parts = []
        if want_weather:
            parts.append(_weather_section(city))
        if want_news:
            parts.append(_news_section())
        if want_fx:
            parts.append(_fx_section())

        result = "\n\n".join(p for p in parts if p)
        result = result[:3500]
    except Exception as e:
        result = f"Sir, the daily briefing failed unexpectedly: {e}"

    _log(result, player)
    if result and player:
        try:
            title = "GAZETE BAŞLIKLARI" if wanted == "haberler" or wanted == "haber" or wanted == "gazete" else "GÜNLÜK BRİFİNG"
            player.show_content(title, result)
        except Exception:
            pass
    return result or "Sir, I couldn't put together any part of the briefing right now."


def _default_city() -> str:
    try:
        identity = load_memory().get("identity", {})
        entry = identity.get("city")
        if isinstance(entry, dict) and entry.get("value"):
            return str(entry["value"]).strip()
    except Exception:
        pass
    return "Istanbul"


def _weather_section(city: str) -> str:
    try:
        url = f"https://wttr.in/{quote(city)}?format=j1&lang=tr"
        r = requests.get(url, headers=_HEADERS, timeout=_TIMEOUT)
        r.raise_for_status()
        data = r.json()

        current = data["current_condition"][0]
        temp_c  = current.get("temp_C", "?")
        feels   = current.get("FeelsLikeC", "?")
        humid   = current.get("humidity", "?")
        try:
            desc = current["lang_tr"][0]["value"]
        except Exception:
            desc = current.get("weatherDesc", [{}])[0].get("value", "")

        today = data["weather"][0]
        tmax  = today.get("maxtempC", "?")
        tmin  = today.get("mintempC", "?")

        return (
            f"Hava durumu ({city}): {desc}, şu an {temp_c}°C (hissedilen {feels}°C), "
            f"nem %{humid}. Bugün en düşük {tmin}°C, en yüksek {tmax}°C."
        )
    except Exception as e:
        return f"Hava durumu ({city}): şu an alınamadı ({e})."


def _news_section() -> str:
    lines = []
    for source_name, feed_url in _NEWS_FEEDS:
        try:
            r = requests.get(feed_url, headers=_HEADERS, timeout=_TIMEOUT)
            r.raise_for_status()
            root = ET.fromstring(r.content)
            titles = [
                (t.text or "").strip()
                for t in root.findall(".//item/title")
                if t.text and t.text.strip()
            ][:_HEADLINES_PER_SOURCE]
            if titles:
                lines.append(f"{source_name}: " + " | ".join(titles))
        except Exception:
            continue

    if not lines:
        return "Gazete başlıkları: şu an hiçbir kaynaktan alınamadı."
    return "Gazete başlıkları:\n" + "\n".join(lines)


def _fx_section() -> str:
    try:
        r = requests.get(
            "https://api.exchangerate-api.com/v4/latest/USD",
            headers=_HEADERS, timeout=_TIMEOUT,
        )
        r.raise_for_status()
        rates = r.json().get("rates", {})
        usd_try = rates["TRY"]
        eur_try = rates["TRY"] / rates["EUR"]
        return f"Döviz: Dolar {usd_try:.2f} TL, Euro {eur_try:.2f} TL."
    except Exception as e:
        return f"Döviz: kur bilgisi şu an alınamadı ({e})."


def _log(message: str, player=None) -> None:
    print(f"[DailyBriefing] {message[:200]}")
    if player:
        try:
            player.write_log(f"JARVIS: {message}")
        except Exception:
            pass
