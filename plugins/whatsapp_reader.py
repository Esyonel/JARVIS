"""
JARVIS plugin — search/summarize the user's own exported WhatsApp groups.

Reads local exports produced by D:\\nu\\whatsapp-exporter (the user's own
authenticated WhatsApp Web session, run separately — this plugin only reads
the resulting local messages.json files, it doesn't touch WhatsApp itself).
Use project_launcher to open the exporter tool and run a fresh export first.
"""

import json
import re
from pathlib import Path

PLUGIN = {
    "name": "whatsapp_reader",
    "description": (
        "Searches or summarizes a previously-exported WhatsApp group chat "
        "(exported via the whatsapp-exporter tool, saved locally under "
        "D:\\nu\\whatsapp-exporter\\exports). Use for: 'X grubunda ne "
        "konuşulmuş özetle', 'şu grupta mazot hakkında ne yazılmış', "
        "'grup sohbetinde Y kelimesini ara'. If no export exists yet for that "
        "group, say so and suggest running the exporter first (project_launcher "
        "can open 'whatsapp-exporter'). Give the group name as it appears in "
        "the WhatsApp group (partial match is fine)."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "group_name": {
                "type": "STRING",
                "description": "Name (or fragment) of the WhatsApp group to read, e.g. 'Kramtau Beton'.",
            },
            "query": {
                "type": "STRING",
                "description": (
                    "A keyword/phrase to search for within the group's messages. "
                    "Optional — if omitted, a general summary of recent messages is given instead."
                ),
            },
        },
        "required": ["group_name"],
    },
}

_EXPORTS_DIR = Path("D:/nu/whatsapp-exporter/exports")
_SUMMARY_WINDOW = 60  # most recent text messages considered for the summary


def run(parameters: dict, player=None, session_memory=None) -> str:
    group_name = (parameters.get("group_name") or "").strip()
    query = (parameters.get("query") or "").strip()

    if not group_name:
        msg = "Sir, I need a group name to look up."
        _log(msg, player)
        return msg

    group_dir = _find_group(group_name)
    if group_dir is None:
        msg = (
            f"Sir, no export found for a group matching '{group_name}'. "
            "Run the WhatsApp exporter first to create one."
        )
        _log(msg, player)
        return msg

    try:
        data = json.loads((group_dir / "messages.json").read_text(encoding="utf-8"))
    except Exception as e:
        msg = f"Sir, I couldn't read the export for '{group_dir.name}': {e}"
        _log(msg, player)
        return msg

    messages = data.get("messages", [])
    if not messages:
        msg = f"'{data.get('groupName', group_dir.name)}' export is empty."
        _log(msg, player)
        return msg

    result = _search(data, messages, query) if query else _summarize(data, messages)
    _log(result, player)
    return result[:3000]


def _find_group(name: str) -> Path | None:
    if not _EXPORTS_DIR.exists():
        return None
    name_lower = name.lower()
    candidates = [
        d for d in _EXPORTS_DIR.iterdir()
        if d.is_dir() and (d / "messages.json").exists() and name_lower in d.name.lower()
    ]
    if not candidates:
        return None
    candidates.sort(key=lambda d: len(d.name))
    return candidates[0]


def _search(data: dict, messages: list[dict], query: str) -> str:
    q = query.lower()
    hits = [m for m in messages if q in (m.get("body") or "").lower()]
    group_name = data.get("groupName", "")

    if not hits:
        return f"'{group_name}' grubunda '{query}' geçen mesaj bulunamadı ({len(messages)} mesaj tarandı)."

    lines = [f"'{group_name}' grubunda '{query}' geçen {len(hits)} mesaj bulundu:"]
    for m in hits[-10:]:
        date = (m.get("timestamp") or "")[:10]
        body = (m.get("body") or "").strip().replace("\n", " ")[:180]
        lines.append(f"- [{date}] {body}")
    if len(hits) > 10:
        lines.append(f"(...son 10 tanesi gösteriliyor, toplam {len(hits)})")
    return "\n".join(lines)


def _summarize(data: dict, messages: list[dict]) -> str:
    group_name = data.get("groupName", "")
    total = len(messages)
    dates = [m.get("timestamp", "")[:10] for m in messages if m.get("timestamp")]
    date_range = f"{min(dates)} — {max(dates)}" if dates else "bilinmiyor"
    media_count = sum(1 for m in messages if m.get("hasMedia"))

    text_bodies = [m.get("body", "").strip() for m in messages if m.get("body", "").strip()]
    recent = text_bodies[-_SUMMARY_WINDOW:]

    header = (
        f"'{group_name}': {total} mesaj ({date_range} arası), {media_count} medya. "
    )

    if not recent:
        return header + "Metin içerikli mesaj yok, sadece medya/etkinlik kaydı."

    ai_summary = _ai_summarize(group_name, recent)
    if ai_summary:
        return header + ai_summary

    preview = " | ".join(recent[-8:])[:1000]
    return header + "Son mesajlar: " + preview


def _ai_summarize(group_name: str, texts: list[str]) -> str:
    try:
        from config import get_config
        key = get_config().get("gemini_api_key")
        if not key:
            return ""

        from google import genai
        client = genai.Client(api_key=key)

        joined = "\n".join(f"- {t}" for t in texts)[:8000]
        prompt = (
            f"Bu bir WhatsApp grup sohbetinin ('{group_name}') son mesajları. "
            "Türkçe, 3-5 cümleyle, ana konuları ve varsa önemli kararları/talepleri özetle. "
            "Kişi isimlerini uydurma, mesajlarda geçmeyen bilgi ekleme.\n\n"
            f"{joined}"
        )
        resp = client.models.generate_content(model="gemini-flash-latest", contents=prompt)
        return (resp.text or "").strip()
    except Exception as e:
        print(f"[WhatsAppReader] AI summary failed: {e}")
        return ""


def _log(message: str, player=None) -> None:
    print(f"[WhatsAppReader] {message[:200]}")
    if player:
        try:
            player.write_log(f"JARVIS: {message}")
        except Exception:
            pass
