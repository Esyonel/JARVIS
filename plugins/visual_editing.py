"""Local live background replacement and Replicate virtual try-on."""

import base64
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

import requests

from config import get_config


PLUGIN = {
    "name": "visual_editing",
    "description": "Canlı videoda arka planı değiştirir veya fotoğrafta sanal kıyafet denemesi yapar.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "string",
                "description": "live_background veya virtual_try_on",
            },
            "image_path": {
                "type": "string",
                "description": "Kişi fotoğrafının yerel yolu (virtual_try_on için).",
            },
            "garment_path": {
                "type": "string",
                "description": "Kıyafet fotoğrafının yerel yolu (virtual_try_on için).",
            },
            "background_path": {
                "type": "string",
                "description": "Canlı video arka plan resmi; verilmezse arka plan rengi kullanılır.",
            },
            "background_color": {
                "type": "string",
                "description": "Canlı video için BGR renk, örnek: 20,20,20.",
                "default": "20,20,20",
            },
            "output_path": {
                "type": "string",
                "description": "Kıyafet değiştirme sonucunun kaydedileceği dosya yolu.",
                "default": "visual_edit_output.png",
            },
        },
        "required": ["action"],
    },
}

_REPLICATE_API = "https://api.replicate.com/v1"
_TRY_ON_MODEL = "cuuupid/idm-vton"
_BACKGROUND_MODEL = "851-labs/background-remover"


def _local_path(value: str) -> Path:
    return Path(value).expanduser().resolve()


def _live_background(parameters: dict[str, Any]) -> str:
    try:
        import cv2
    except ImportError:
        return "Canlı arka plan için OpenCV kurulu değil."

    backend = cv2.CAP_DSHOW if sys.platform == "win32" else cv2.CAP_ANY
    camera = cv2.VideoCapture(0, backend)
    if not camera.isOpened():
        return "Kamera açılamadı."

    background_path = parameters.get("background_path", "").strip()
    background = None
    if background_path:
        background = cv2.imread(str(_local_path(background_path)))
        if background is None:
            camera.release()
            return "Arka plan resmi okunamadı."

    try:
        subtractor = cv2.createBackgroundSubtractorMOG2(
            history=500, varThreshold=32, detectShadows=False
        )
        color_parts = [int(part.strip()) for part in parameters.get("background_color", "20,20,20").split(",")]
        if len(color_parts) != 3 or any(part < 0 or part > 255 for part in color_parts):
            raise ValueError
        color = tuple(color_parts)
    except ValueError:
        camera.release()
        return "background_color BGR biçiminde üç sayı olmalı, örnek: 20,20,20."

    frames_read = 0
    read_failures = 0
    try:
        while True:
            ok, frame = camera.read()
            if not ok:
                read_failures += 1
                if read_failures >= 3:
                    break
                continue
            frames_read += 1
            read_failures = 0
            mask = subtractor.apply(frame)
            mask = cv2.threshold(mask, 220, 255, cv2.THRESH_BINARY)[1]
            mask = cv2.medianBlur(mask, 5)
            if background is None:
                replacement = frame.copy()
                replacement[:] = color
            else:
                replacement = cv2.resize(background, (frame.shape[1], frame.shape[0]))
            foreground = cv2.bitwise_and(frame, frame, mask=mask)
            inverse = cv2.bitwise_not(mask)
            replacement = cv2.bitwise_and(replacement, replacement, mask=inverse)
            cv2.imshow("JARVIS - Live Background", cv2.add(foreground, replacement))
            if cv2.waitKey(1) & 0xFF == ord("q"):
                break
    finally:
        camera.release()
        cv2.destroyAllWindows()
        cv2.waitKey(1)
    if frames_read == 0:
        return "Kameradan görüntü alınamadı. Kamera başka bir uygulama tarafından kullanılıyor olabilir."
    return "Canlı arka plan değişimi tamamlandı."


def _data_uri(path: Path) -> str:
    mime = "image/png" if path.suffix.lower() == ".png" else "image/jpeg"
    return f"data:{mime};base64," + base64.b64encode(path.read_bytes()).decode("ascii")


def _replicate_token(parameters: dict[str, Any]) -> str:
    token = parameters.get("replicate_api_token", "").strip()
    if token:
        return token
    token = os.getenv("REPLICATE_API_TOKEN", "").strip()
    if token:
        return token
    return str(get_config().get("replicate_api_token", "")).strip()


def _virtual_try_on(parameters: dict[str, Any]) -> str:
    image_path = _local_path(parameters.get("image_path", ""))
    garment_path = _local_path(parameters.get("garment_path", ""))
    if not image_path.is_file() or not garment_path.is_file():
        return "Kişi ve kıyafet fotoğraflarının yerel yolları geçerli olmalı."

    token = _replicate_token(parameters)
    if not token:
        return "Sanal kıyafet denemesi için REPLICATE_API_TOKEN yapılandırılmamış."

    try:
        response = requests.post(
            f"{_REPLICATE_API}/models/{_TRY_ON_MODEL}/predictions",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json={
                "input": {
                    "human_img": _data_uri(image_path),
                    "garm_img": _data_uri(garment_path),
                    "garment_des": parameters.get("garment_description", "clothing"),
                }
            },
            timeout=60,
        )
        response.raise_for_status()
        prediction = response.json()
        prediction_url = prediction.get("urls", {}).get("get")
        if not prediction_url:
            return "Replicate tahmin adresi döndürmedi."

        for _ in range(60):
            status_response = requests.get(
                prediction_url,
                headers={"Authorization": f"Bearer {token}"},
                timeout=30,
            )
            status_response.raise_for_status()
            result = status_response.json()
            if result.get("status") == "succeeded":
                output = result.get("output")
                output_url = output[0] if isinstance(output, list) else output
                if not output_url:
                    return "Model çıktı üretmedi."
                output_path = _local_path(parameters.get("output_path", "visual_edit_output.png"))
                output_path.parent.mkdir(parents=True, exist_ok=True)
                output_path.write_bytes(requests.get(output_url, timeout=60).content)
                return f"Sanal kıyafet denemesi tamamlandı: {output_path}"
            if result.get("status") in {"failed", "canceled"}:
                return f"Sanal kıyafet denemesi başarısız: {result.get('error', 'bilinmeyen hata')}"
            time.sleep(2)
        return "Sanal kıyafet denemesi zaman aşımına uğradı."
    except requests.RequestException as error:
        return f"Görsel model bağlantısı başarısız: {error}"
    except (OSError, json.JSONDecodeError) as error:
        return f"Görsel dosyası işlenemedi: {error}"


def _image_background_remove(parameters: dict[str, Any]) -> str:
    image_path = _local_path(parameters.get("image_path", ""))
    if not image_path.is_file():
        return "Arka planı silinecek resmin yerel yolu geçerli olmalı."

    token = _replicate_token(parameters)
    if not token:
        return "Resim arka planı silme için REPLICATE_API_TOKEN yapılandırılmamış."

    try:
        response = requests.post(
            f"{_REPLICATE_API}/models/{_BACKGROUND_MODEL}/predictions",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json={"input": {"image": _data_uri(image_path)}},
            timeout=60,
        )
        response.raise_for_status()
        prediction_url = response.json().get("urls", {}).get("get")
        if not prediction_url:
            return "Replicate tahmin adresi döndürmedi."

        for _ in range(60):
            result = requests.get(
                prediction_url,
                headers={"Authorization": f"Bearer {token}"},
                timeout=30,
            ).json()
            if result.get("status") == "succeeded":
                output_url = result.get("output")
                output_path = _local_path(parameters.get("output_path", "background_removed.png"))
                output_path.parent.mkdir(parents=True, exist_ok=True)
                output_path.write_bytes(requests.get(output_url, timeout=60).content)
                return f"Resim arka planı silindi: {output_path}"
            if result.get("status") in {"failed", "canceled"}:
                return f"Arka plan silme başarısız: {result.get('error', 'bilinmeyen hata')}"
            time.sleep(2)
        return "Resim arka planı silme zaman aşımına uğradı."
    except requests.RequestException as error:
        return f"Arka plan modeli bağlantısı başarısız: {error}"
    except OSError as error:
        return f"Görsel dosyası işlenemedi: {error}"


def run(parameters: dict, player=None, session_memory=None) -> str:
    action = parameters.get("action", "").strip().lower()
    if action == "live_background":
        return _live_background(parameters)
    if action == "virtual_try_on":
        return _virtual_try_on(parameters)
    if action == "image_background_remove":
        return _image_background_remove(parameters)
    return "action live_background veya virtual_try_on olmalı."
