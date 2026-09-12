"""Query NVIDIA's Integrate API (https://integrate.api.nvidia.com/) for advanced
AI model responses — Minimax, Llama, Mixtral, and other NVIDIA-hosted models.

Native action module (see main.py's "nvidia_integrate_api" tool declaration and
its _execute_tool elif branch) rather than a plugins/ entry, since the tool name
is already reserved as a core/static tool declaration and plugins/ rejects any
plugin whose name collides with one.
"""

import json
import requests

from config import get_config
from core.api_usage import record as record_api_usage


def nvidia_integrate_api(parameters: dict, player=None) -> str:
    """Send a prompt to an NVIDIA-hosted chat model and return its reply.

    Parameters
    ----------
    parameters : dict
        'prompt' (required). Optional: 'model', 'temperature', 'top_p',
        'max_tokens', 'api_key' (falls back to config's nvidia_integrate_api_key).
    """
    prompt = parameters.get("prompt")
    if not prompt:
        return "Error: 'prompt' is a required parameter."

    api_key = parameters.get("api_key") or get_config().get("nvidia_integrate_api_key")
    if not api_key:
        return "Error: no NVIDIA Integrate API key available (configure nvidia_integrate_api_key)."

    model       = parameters.get("model", "minimaxai/minimax-m3")
    temperature = parameters.get("temperature", 1)
    top_p       = parameters.get("top_p", 0.95)
    max_tokens  = parameters.get("max_tokens", 8192)

    invoke_url = "https://integrate.api.nvidia.com/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Accept": "application/json",
    }
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": temperature,
        "top_p": top_p,
        "max_tokens": max_tokens,
        "stream": False,
    }

    try:
        response = requests.post(invoke_url, headers=headers, json=payload, timeout=30)
        response.raise_for_status()
        result = response.json()

        choices = result.get("choices") or []
        if choices:
            record_api_usage("nvidia-1")
            return choices[0].get("message", {}).get("content", "No response received.")
        return f"Error: Unexpected response format. {result}"

    except requests.exceptions.RequestException as e:
        return f"Error querying NVIDIA API: {e}"
    except json.JSONDecodeError:
        return "Error: Failed to parse API response as JSON."
