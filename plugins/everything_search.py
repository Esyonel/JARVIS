"""
JARVIS Plugin: everything_search

Instant, whole-disk file search via voidtools' Everything, through its built-in
local HTTP server — reads the live NTFS index Everything already maintains,
instead of walking the filesystem live like file_controller's "find" action
(actions/file_controller.py's find_files: rglob() capped at 500 dirs, slow and
incomplete on a large/full drive).

Requires Everything's HTTP server enabled: Tools > Options > HTTP Sunucusu,
bound to 127.0.0.1, port set to match _PORT below.
"""
import json
import urllib.parse
import urllib.request
from typing import Any, Dict

PLUGIN = {
    "name": "everything_search",
    "description": (
        "Bilgisayardaki herhangi bir dosya veya klasörü adına göre ANINDA bulur — "
        "Everything programının önceden çıkarılmış NTFS indeksini sorgular, canlı disk "
        "taraması yapmaz, sonuç milisaniyeler içinde döner. Kullanıcı 'şu dosyayı bul', "
        "'bilgisayarımda X diye bir şey var mı', bir dosya/klasör adı veya uzantı söylediğinde "
        "kullan. file_controller'ın 'find' aksiyonundan çok daha hızlı ve tüm diski kapsar."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "query": {
                "type": "STRING",
                "description": "Aranacak dosya/klasör adı veya adının bir parçası",
            },
            "extension": {
                "type": "STRING",
                "description": "İsteğe bağlı: sonucu sadece bu uzantıyla sınırla (ör. pdf, docx, py)",
            },
            "max_results": {
                "type": "INTEGER",
                "description": "Döndürülecek maksimum sonuç sayısı (varsayılan 15, en fazla 50)",
            },
        },
        "required": ["query"],
    },
}

_PORT = 8080
_BASE_URL = f"http://127.0.0.1:{_PORT}/"


def _human_size(raw) -> str:
    try:
        n = float(raw)
    except (TypeError, ValueError):
        return ""
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024:
            return f"{n:.0f}{unit}" if unit == "B" else f"{n:.1f}{unit}"
        n /= 1024
    return f"{n:.1f}PB"


def run(parameters: Dict[str, Any], player=None, session_memory=None) -> str:
    query = str(parameters.get("query", "")).strip()
    if not query:
        return "Aranacak bir dosya/klasör adı belirtilmedi."

    extension  = str(parameters.get("extension", "")).strip().lstrip(".")
    try:
        max_results = min(int(parameters.get("max_results", 15) or 15), 50)
    except (TypeError, ValueError):
        max_results = 15

    search_expr = f"{query} ext:{extension}" if extension else query

    query_params = {
        "search": search_expr,
        "json": "1",
        "count": str(max_results),
        "path_column": "1",
        "size_column": "1",
    }
    url = _BASE_URL + "?" + urllib.parse.urlencode(query_params)

    try:
        with urllib.request.urlopen(url, timeout=3) as resp:
            data = json.loads(resp.read().decode("utf-8", errors="replace"))
    except Exception as e:
        return (
            "Everything'in arama servisine ulaşamadım. Everything açık olmalı ve "
            f"Tools > Options > HTTP Sunucusu'ndan 127.0.0.1:{_PORT} adresine "
            f"bağlı HTTP sunucusu etkin olmalı. ({e})"
        )

    results = data.get("results", []) if isinstance(data, dict) else []
    total   = data.get("totalResults", len(results)) if isinstance(data, dict) else len(results)

    if not results:
        return f"'{query}' için hiçbir dosya/klasör bulunamadı."

    lines = []
    for r in results[:max_results]:
        name  = r.get("name", "?")
        path  = r.get("path", "")
        size  = _human_size(r.get("size"))
        icon  = "📁" if r.get("type") == "folder" else "📄"
        size_part = f" ({size})" if size else ""
        lines.append(f"{icon} {name}{size_part} — {path}")

    header = (
        f"{total} sonuçtan ilk {len(lines)} tanesi:"
        if total and total > len(lines)
        else f"{len(lines)} sonuç bulundu:"
    )
    return header + "\n" + "\n".join(lines)
