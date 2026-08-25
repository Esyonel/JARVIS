"""
JARVIS Autonomous MCP & AITMPL Component Manager
Enables JARVIS to autonomously search, install, register, and manage MCP servers,
aitmpl templates, skills, and Python/Node packages, and auto-update kurulum.md.
"""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent
AGENTS_DIR = WORKSPACE_ROOT / ".agents"
WORKSPACE_MCP_CONFIG = AGENTS_DIR / "mcp_config.json"
GLOBAL_MCP_CONFIG = Path.home() / ".gemini" / "config" / "mcp_config.json"
KURULUM_MD = WORKSPACE_ROOT / "kurulum.md"


class MCPManager:
    """Manages MCP servers, tool discovery, installation, and registration."""

    @staticmethod
    def _ensure_dir(path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)

    @classmethod
    def get_config(cls, target: str = "workspace") -> Dict[str, Any]:
        cfg_path = WORKSPACE_MCP_CONFIG if target == "workspace" else GLOBAL_MCP_CONFIG
        if cfg_path.exists():
            try:
                with open(cfg_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {"mcpServers": {}}

    @classmethod
    def save_config(cls, config_data: Dict[str, Any], target: str = "workspace") -> bool:
        cfg_path = WORKSPACE_MCP_CONFIG if target == "workspace" else GLOBAL_MCP_CONFIG
        cls._ensure_dir(cfg_path)
        try:
            with open(cfg_path, "w", encoding="utf-8") as f:
                json.dump(config_data, f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            print(f"[MCPManager] Config save error: {e}")
            return False

    @classmethod
    def register_server(
        cls,
        name: str,
        command: str,
        args: Optional[List[str]] = None,
        env: Optional[Dict[str, str]] = None,
        target: str = "all",
    ) -> bool:
        """Register an MCP server definition into mcp_config.json."""
        server_entry: Dict[str, Any] = {"command": command, "args": args or []}
        if env:
            server_entry["env"] = env

        targets = ["workspace", "global"] if target == "all" else [target]
        success = True
        for tgt in targets:
            cfg = cls.get_config(tgt)
            if "mcpServers" not in cfg:
                cfg["mcpServers"] = {}
            cfg["mcpServers"][name] = server_entry
            if not cls.save_config(cfg, tgt):
                success = False
        return success

    @classmethod
    def install_npm_mcp(
        cls,
        package_name: str,
        server_name: Optional[str] = None,
        args: Optional[List[str]] = None,
        env: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """Install an npm-based MCP server globally and register it."""
        name = server_name or package_name.split("/")[-1]
        cmd = ["npm", "install", "-g", package_name]
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=300, shell=True)
            if res.returncode != 0:
                return {
                    "success": False,
                    "error": f"npm install failed: {res.stderr or res.stdout}",
                }
        except Exception as e:
            return {"success": False, "error": str(e)}

        # Register server
        registered = cls.register_server(
            name=name,
            command="npx",
            args=["-y", package_name] + (args or []),
            env=env,
        )

        cls.append_to_kurulum(
            component_name=f"MCP: {name} ({package_name})",
            component_type="Model Context Protocol Server",
            command=f"npm install -g {package_name}",
            description=f"Otonom olarak kurulan {name} MCP sunucusu.",
        )

        return {
            "success": True,
            "server_name": name,
            "registered": registered,
            "message": f"{package_name} başarıyla kuruldu ve mcp_config.json'a eklendi.",
        }

    @classmethod
    def install_python_package(cls, package_name: str, import_name: Optional[str] = None) -> Dict[str, Any]:
        """Install Python library and register into requirements/kurulum.md."""
        cmd = [sys.executable, "-m", "pip", "install", package_name]
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            if res.returncode != 0:
                return {"success": False, "error": res.stderr or res.stdout}
        except Exception as e:
            return {"success": False, "error": str(e)}

        cls.append_to_kurulum(
            component_name=f"Python: {package_name}",
            component_type="Python Kütüphanesi",
            command=f"pip install {package_name}",
            description=f"JARVIS tarafından otonom kurulan {package_name} paketi.",
        )
        return {"success": True, "message": f"{package_name} başarıyla kuruldu."}

    @classmethod
    def append_to_kurulum(cls, component_name: str, component_type: str, command: str, description: str) -> None:
        """Automatically updates kurulum.md with newly installed component."""
        if not KURULUM_MD.exists():
            return
        try:
            entry = (
                f"\n\n### 📦 Yeni Eklenen Bileşen: {component_name}\n"
                f"- **Tür:** {component_type}\n"
                f"- **Açıklama:** {description}\n"
                f"- **Kurulum Komutu:**\n"
                f"```powershell\n{command}\n```\n"
            )
            with open(KURULUM_MD, "a", encoding="utf-8") as f:
                f.write(entry)
        except Exception as e:
            print(f"[MCPManager] Failed to append to kurulum.md: {e}")


mcp_manager = MCPManager()
