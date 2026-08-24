import os
import platform
import subprocess

# Plugin metadata used by JARVIS to discover and describe the plugin
PLUGIN = {
    "name": "computer_full_control",
    "description": "Bilgisayarı tamamen yönetebilecek yetenekler: kapatma, yeniden başlatma, uyku moda alma, kilitleme ve temel ses kontrolü.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "command": {
                "type": "STRING",
                "description": "Çalıştırılacak komut. 'shutdown', 'restart', 'sleep', 'lock', 'volume_up', 'volume_down', 'mute' veya 'unmute' değerlerinden biri."
            },
            "args": {
                "type": "STRING",
                "description": "Komut için isteğe bağlı ek argümanlar. Gerekli değildir."
            }
        },
        "required": ["command"]
    }
}


def _execute_windows(command: str, args: str = "") -> str:
    try:
        if command == "shutdown":
            os.system("shutdown /s /t 0")
        elif command == "restart":
            os.system("shutdown /r /t 0")
        elif command == "sleep":
            os.system("rundll32.exe powrprof.dll,SetSuspendState 0,1,0")
        elif command == "lock":
            os.system("rundll32.exe user32.dll,LockWorkStation")
        elif command == "volume_up":
            # 5000 birim ses artırma (nircmd gerektirir)
            os.system("nircmd.exe changesysvolume 5000")
        elif command == "volume_down":
            os.system("nircmd.exe changesysvolume -5000")
        elif command == "mute":
            os.system("nircmd.exe mutesysvolume 1")
        elif command == "unmute":
            os.system("nircmd.exe mutesysvolume 0")
        else:
            return f"Bilinmeyen komut: {command}"
        return f"{command} komutu başarıyla yürütüldü."
    except Exception as e:
        return f"{command} komutu çalıştırılırken hata oluştu: {e}"


def _execute_unix(command: str, args: str = "") -> str:
    try:
        if command == "shutdown":
            subprocess.run(["shutdown", "now"], check=True)
        elif command == "restart":
            subprocess.run(["reboot"], check=True)
        elif command == "sleep":
            subprocess.run(["systemctl", "suspend"], check=True)
        elif command == "lock":
            # gnome-screensaver-command or loginctl depending on ortam
            if subprocess.run(["which", "loginctl"], capture_output=True).returncode == 0:
                subprocess.run(["loginctl", "lock-session"], check=True)
            else:
                subprocess.run(["gnome-screensaver-command", "-l"], check=True)
        elif command == "volume_up":
            subprocess.run(["amixer", "-D", "pulse", "sset", "Master", "5%+"], check=True)
        elif command == "volume_down":
            subprocess.run(["amixer", "-D", "pulse", "sset", "Master", "5%-"], check=True)
        elif command == "mute":
            subprocess.run(["amixer", "-D", "pulse", "sset", "Master", "mute"], check=True)
        elif command == "unmute":
            subprocess.run(["amixer", "-D", "pulse", "sset", "Master", "unmute"], check=True)
        else:
            return f"Bilinmeyen komut: {command}"
        return f"{command} komutu başarıyla yürütüldü."
    except Exception as e:
        return f"{command} komutu çalıştırılırken hata oluştu: {e}"


def run(parameters: dict, player=None, session_memory=None) -> str:
    """Execute a system control command.

    Parameters
    ----------
    parameters: dict
        Must contain a ``command`` key and optional ``args``.
    player, session_memory: Ignored – kept for plugin signature compatibility.

    Returns
    -------
    str
        A short Turkish sentence that JARVIS can speak back to the user.
    """
    try:
        command = str(parameters.get("command", "")).strip().lower()
        args = str(parameters.get("args", "")).strip()
        if not command:
            return "Komut belirtilmedi. Lütfen bir komut girin."
        current_os = platform.system()
        if current_os == "Windows":
            return _execute_windows(command, args)
        else:
            # Assume Linux/macOS (both are Unix‑like for our purposes)
            return _execute_unix(command, args)
    except Exception as exc:
        return f"Sistem kontrolü sırasında beklenmeyen bir hata oluştu: {exc}"
