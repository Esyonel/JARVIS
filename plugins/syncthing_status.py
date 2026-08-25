"""
JARVIS plugin — reports local Syncthing sync status: connected devices,
per-folder up-to-date/syncing state, and any file conflicts or errors.

Needs Syncthing's REST API key (Settings -> Actions -> Show ID / API Key in
the Syncthing web UI, http://127.0.0.1:8384) stored in config/api_keys.json
as 'syncthing_api_key'. Never fetched automatically — JARVIS has no business
reading another app's config file to extract a key on its own.
"""

import requests

from memory.config_manager import load_api_keys

PLUGIN = {
    "name": "syncthing_status",
    "description": (
        "Reports the local Syncthing instance's status — connected devices, "
        "per-folder sync state, and file conflicts/errors. Use for: "
        "'Syncthing durumu nedir', 'dosya çakışması var mı', 'senkronizasyon "
        "tamamlandı mı'. Requires syncthing_api_key set in config/api_keys.json "
        "— returns setup instructions if missing."
    ),
    "parameters": {"type": "OBJECT", "properties": {}, "required": []},
}

_DEFAULT_URL = "http://127.0.0.1:8384"
_TIMEOUT = 8


def _get(base_url: str, path: str, api_key: str):
    resp = requests.get(f"{base_url}{path}", headers={"X-API-Key": api_key}, timeout=_TIMEOUT)
    resp.raise_for_status()
    return resp.json()


def run(parameters: dict, player=None, session_memory=None) -> str:
    keys = load_api_keys()
    api_key = keys.get("syncthing_api_key")
    base_url = keys.get("syncthing_url") or _DEFAULT_URL
    if not api_key:
        return (
            "Sir, Syncthing API anahtarı yapılandırılmamış. Syncthing web "
            "arayüzünde (http://127.0.0.1:8384) Ayarlar -> Genel'den API "
            "anahtarını al ve config/api_keys.json içine 'syncthing_api_key' "
            "olarak ekle."
        )

    try:
        status = _get(base_url, "/rest/system/status", api_key)
        connections = _get(base_url, "/rest/system/connections", api_key)
        folders = _get(base_url, "/rest/config/folders", api_key)
    except requests.RequestException as e:
        return f"Sir, Syncthing'e ulaşamadım ({base_url}): {e}"

    connected = sum(
        1 for c in connections.get("connections", {}).values() if c.get("connected")
    )
    total_devices = len(connections.get("connections", {}))

    lines = [f"Syncthing çalışıyor, sürüm {status.get('version', '?')}. "
             f"{connected}/{total_devices} cihaz bağlı."]

    for folder in folders:
        fid = folder.get("id")
        label = folder.get("label") or fid
        try:
            completion = _get(base_url, f"/rest/db/status?folder={fid}", api_key)
            errors = _get(base_url, f"/rest/folder/errors?folder={fid}", api_key)
        except requests.RequestException:
            lines.append(f"- {label}: durum okunamadı.")
            continue

        state = completion.get("state", "bilinmiyor")
        err_count = len(errors.get("errors", []) or [])
        state_tr = {"idle": "güncel", "syncing": "senkronize ediliyor",
                    "scanning": "taranıyor", "error": "hata"}.get(state, state)
        if err_count:
            lines.append(f"- {label}: {state_tr}, {err_count} hata/çakışma var.")
        else:
            lines.append(f"- {label}: {state_tr}.")

    result = "\n".join(lines)
    if player:
        try:
            player.write_log(f"JARVIS: {result}")
        except Exception:
            pass
    return result
