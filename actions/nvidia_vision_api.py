"""Analyze an image URL using NVIDIA's vision-capable models, with optional
extended "thinking" for more detailed analysis.

Native action module (see main.py's "nvidia_vision_api" tool declaration and
its _execute_tool elif branch) rather than a plugins/ entry, since the tool name
is already reserved as a core/static tool declaration and plugins/ rejects any
plugin whose name collides with one.
"""

import json
import requests

from config import get_config
from core.api_usage import record as record_api_usage


def nvidia_vision_api(parameters: dict, player=None) -> str:
    """Send an image URL + question to an NVIDIA-hosted vision model and return its reply.

    Parameters
    ----------
    parameters : dict
        'image_url' and 'question' (required). Optional: 'api_key' (falls back
        to config's nvidia_vision_api_key), 'model', 'enable_thinking',
        'max_tokens', 'temperature', 'top_p'.
    """
    image_url = (parameters.get("image_url") or "").strip()
    question  = (parameters.get("question") or "").strip()
    if not image_url or not question:
        return "Error: 'image_url' and 'question' are required parameters."

    api_key = (parameters.get("api_key") or "").strip() or get_config().get("nvidia_vision_api_key")
    if not api_key:
        return "Error: no NVIDIA Vision API key available (configure nvidia_vision_api_key)."

    model           = parameters.get("model", "minimaxai/minimax-m3")
    enable_thinking = parameters.get("enable_thinking", True)
    max_tokens      = parameters.get("max_tokens", 16384)
    temperature     = parameters.get("temperature", 1)
    top_p           = parameters.get("top_p", 0.95)

    invoke_url = "https://integrate.api.nvidia.com/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Accept": "application/json",
    }
    payload = {
        "model": model,
        "messages": [{
            "role": "user",
            "content": [
                {"type": "text", "text": question},
                {"type": "image_url", "image_url": {"url": image_url}},
            ],
        }],
        "max_tokens": max_tokens,
        "temperature": temperature,
        "top_p": top_p,
        "stream": False,
    }
    if enable_thinking:
        payload["chat_template_kwargs"] = {"enable_thinking": True}

    try:
        response = requests.post(invoke_url, headers=headers, json=payload, timeout=60)
        response.raise_for_status()
        result = response.json()

        choices = result.get("choices") or []
        if choices:
            record_api_usage("nvidia-2")
            return choices[0].get("message", {}).get("content", "No response received.")
        return f"Error: Unexpected response format. {result}"

    except requests.exceptions.RequestException as e:
        return f"Error querying NVIDIA Vision API: {e}"
    except json.JSONDecodeError:
        return "Error: Failed to parse API response as JSON."
