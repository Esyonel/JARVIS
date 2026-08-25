"""
JARVIS Plugin: mcp_aitmpl_installer
Enables JARVIS to autonomously install MCP servers, aitmpl templates, skills, and Python libraries,
register them into mcp_config.json, and auto-sync kurulum.md.
"""
from typing import Any, Dict
from core.mcp_manager import mcp_manager

PLUGIN = {
    "name": "mcp_aitmpl_installer",
    "description": (
        "Otonom olarak aitmpl.com şablonlarını, Model Context Protocol (MCP) sunucularını, "
        "Python paketlerini kurar, mcp_config.json'a kaydeder ve kurulum.md dosyasını otomatik günceller."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "description": "Yapılacak işlem: 'install_mcp', 'install_python', 'list_mcps', 'register_existing'",
            },
            "package_name": {
                "type": "STRING",
                "description": "Kurulacak npm MCP paketi adı (@modelcontextprotocol/server-filesystem vb.) veya Python kütüphanesi.",
            },
            "server_name": {
                "type": "STRING",
                "description": "İsteğe bağlı özel MCP sunucu kimliği (ör: brave-search).",
            },
            "command": {
                "type": "STRING",
                "description": "Doğrudan çalıştırılacak komut (register_existing için).",
            },
            "args": {
                "type": "ARRAY",
                "items": {"type": "STRING"},
                "description": "MCP sunucusuna iletilecek argümanlar listesi.",
            },
        },
        "required": ["action"],
    },
}


def run(parameters: Dict[str, Any], player=None, session_memory=None) -> str:
    action = str(parameters.get("action", "")).strip()
    package_name = str(parameters.get("package_name", "")).strip()
    server_name = str(parameters.get("server_name", "")).strip()
    command = str(parameters.get("command", "")).strip()
    args = parameters.get("args", [])

    if action == "install_mcp":
        if not package_name:
            return "Lütfen kurulacak MCP paket adını belirtin."
        res = mcp_manager.install_npm_mcp(
            package_name=package_name,
            server_name=server_name,
            args=args,
        )
        if res.get("success"):
            return f"✅ {package_name} başarıyla kuruldu, yapılandırıldı ve kurulum.md güncellendi."
        return f"❌ Kurulum hatası: {res.get('error')}"

    elif action == "install_python":
        if not package_name:
            return "Lütfen kurulacak Python paket adını belirtin."
        res = mcp_manager.install_python_package(package_name=package_name)
        if res.get("success"):
            return f"✅ Python paketi {package_name} kuruldu ve kurulum.md güncellendi."
        return f"❌ Python kurulum hatası: {res.get('error')}"

    elif action == "list_mcps":
        cfg = mcp_manager.get_config("workspace")
        servers = cfg.get("mcpServers", {})
        if not servers:
            return "Kayıtlı özel MCP sunucusu bulunamadı."
        lines = [f"- {name}: {info.get('command')} {' '.join(info.get('args', []))}" for name, info in servers.items()]
        return "Yüklü MCP Sunucuları:\n" + "\n".join(lines)

    elif action == "register_existing":
        if not server_name or not command:
            return "Kayıt için server_name ve command zorunludur."
        ok = mcp_manager.register_server(name=server_name, command=command, args=args)
        if ok:
            return f"✅ {server_name} MCP sunucusu başarıyla kaydedildi."
        return f"❌ {server_name} kaydedilemedi."

    return f"Bilinmeyen eylem: {action}"
