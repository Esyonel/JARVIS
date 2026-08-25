"""
JARVIS Action: autonomous_computer_agent
Vision-guided autonomous computer use: captures screen, locates visual UI elements,
and performs mouse clicks, drags, typing, and complex multi-step workflows.
"""
from typing import Any, Dict, List, Optional
import pyautogui

# Safe defaults
pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.2


class AutonomousComputerAgent:
    """Executes human-like mouse and keyboard actions on the desktop."""

    @staticmethod
    def click_coordinate(x: int, y: int, button: str = "left", clicks: int = 1) -> str:
        try:
            pyautogui.click(x=x, y=y, button=button, clicks=clicks)
            return f"✅ ({x}, {y}) koordinatına {clicks} kez tıklandı."
        except Exception as e:
            return f"Tıklama hatası: {e}"

    @staticmethod
    def type_text(text: str, press_enter: bool = False) -> str:
        try:
            import pyperclip
            pyperclip.copy(text)
            pyautogui.hotkey("ctrl", "v")
            if press_enter:
                pyautogui.press("enter")
            return f"✅ '{text}' metni yazıldı."
        except Exception as e:
            return f"Yazma hatası: {e}"

    @staticmethod
    def hotkey(*keys: str) -> str:
        try:
            pyautogui.hotkey(*keys)
            return f"✅ Kısayol çalıştırıldı: {' + '.join(keys)}"
        except Exception as e:
            return f"Kısayol hatası: {e}"

    @staticmethod
    def capture_screen_analysis() -> Dict[str, Any]:
        """Captures screen and prepares it for multi-modal coordinate reasoning."""
        import mss
        from PIL import Image
        with mss.mss() as sct:
            monitor = sct.monitors[1]
            sct_img = sct.grab(monitor)
            img = Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")
            return {"width": img.width, "height": img.height, "status": "Screen captured"}


computer_agent = AutonomousComputerAgent()


def run(action: str, **kwargs) -> str:
    if action == "click":
        return computer_agent.click_coordinate(kwargs.get("x", 0), kwargs.get("y", 0))
    elif action == "type":
        return computer_agent.type_text(kwargs.get("text", ""), kwargs.get("press_enter", False))
    elif action == "hotkey":
        return computer_agent.hotkey(*kwargs.get("keys", []))
    elif action == "capture":
        res = computer_agent.capture_screen_analysis()
        return f"Ekran çözünürlüğü: {res.get('width')}x{res.get('height')}"
    return f"Geçersiz işlem: {action}"
