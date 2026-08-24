"""Plugin to query specific NVIDIA-hosted models (e.g. Wan2.2-animate-2-14b,
nemotron-3.5-lightning-30b-a3b) via NVIDIA's Integrate API.

Same endpoint family as nvidia_integrate_api.py; this plugin exists for
callers who want to name a specific model explicitly. api_key defaults to
the stored nvidia_integrate_api_key in config/api_keys.json if not given.
"""

import json
import requests
from typing import Any, Dict

from config import get_config

PLUGIN = {
    "name": "nvidia_model_query",
    "description": "Query a specific NVIDIA-hosted model (e.g., Wan2.2-animate-2-14b, nemotron-3.5-lightning-30b-a3b) and obtain a short textual response.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "model": {
                "type": "string",
                "description": "Exact name of the NVIDIA model to query."
            },
            "prompt": {
                "type": "string",
                "description": "The prompt or question to send to the model."
            },
            "api_key": {
                "type": "string",
                "description": "NVIDIA Integrate API key. Optional; defaults to the stored key."
            },
            "temperature": {
                "type": "number",
                "description": "Sampling temperature (0.0-2.0).",
                "default": 0.7
            },
            "max_output_tokens": {
                "type": "integer",
                "description": "Maximum number of tokens to generate.",
                "default": 512
            }
        },
        "required": ["model", "prompt"]
    }
}


def run(parameters: Dict[str, Any], player: Any = None, session_memory: Any = None) -> str:
    """Query an NVIDIA-hosted model and return a plain-text response."""
    model = parameters.get("model")
    prompt = parameters.get("prompt")
    api_key = parameters.get("api_key") or get_config().get("nvidia_integrate_api_key")
    temperature = parameters.get("temperature", 0.7)
    max_tokens = parameters.get("max_output_tokens", 512)

    if not model or not prompt:
        return "Error: both 'model' and 'prompt' parameters are required."
    if not api_key:
        return "Error: no NVIDIA API key available (pass one or configure nvidia_integrate_api_key)."

    try:
        response = requests.post(
            "https://integrate.api.nvidia.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Accept": "application/json"},
            json={
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": temperature,
                "max_tokens": max_tokens,
                "stream": False,
            },
            timeout=30,
        )
        response.raise_for_status()
        data = response.json()
        choices = data.get("choices") or []
        if not choices:
            return f"Error: unexpected response format from NVIDIA model {model}."
        return choices[0].get("message", {}).get("content", "").strip() or "Empty response."
    except requests.exceptions.RequestException as e:
        return f"Error while contacting NVIDIA model {model}: {e}"
    except json.JSONDecodeError:
        return "Error: failed to parse NVIDIA API response as JSON."
    except Exception as e:
        return f"Unexpected error while querying NVIDIA model {model}: {e}"
