"""NVIDIA Integrate API Plugin

This plugin enables JARVIS to query NVIDIA's Integrate API (https://integrate.api.nvidia.com/)
which provides access to advanced AI models like Minimax, Claude, GPT-4, and more.

The plugin requires an API key from NVIDIA Build and can optionally specify a model.
It returns the assistant's reply as a plain string.
"""

import json
import requests
from typing import Optional
from core.api_usage import record as record_api_usage


PLUGIN = {
    "name": "nvidia_integrate_api",
    "description": "Query NVIDIA Integrate API for advanced AI model responses.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "api_key": {
                "type": "string",
                "description": "Your NVIDIA Integrate API key (Bearer token from build.nvidia.com)."
            },
            "prompt": {
                "type": "string",
                "description": "The user prompt/message to send to the model."
            },
            "model": {
                "type": "string",
                "description": "Model identifier (e.g., 'minimaxai/minimax-m3', 'meta/llama-3.1-405b-instruct'). Optional; defaults to minimaxai/minimax-m3.",
                "default": "minimaxai/minimax-m3"
            },
            "temperature": {
                "type": "number",
                "description": "Sampling temperature (0-2). Optional; defaults to 1.",
                "default": 1
            },
            "top_p": {
                "type": "number",
                "description": "Top-p sampling (0-1). Optional; defaults to 0.95.",
                "default": 0.95
            },
            "max_tokens": {
                "type": "integer",
                "description": "Maximum output tokens. Optional; defaults to 8192.",
                "default": 8192
            }
        },
        "required": ["api_key", "prompt"]
    }
}


def run(
    parameters: dict,
    player=None,
    session_memory=None
) -> str:
    """Execute NVIDIA Integrate API request.

    Parameters
    ----------
    parameters : dict
        Must contain 'api_key' and 'prompt'. Optional: 'model', 'temperature', 'top_p', 'max_tokens'
    player : unused
        Kept for plugin signature compatibility
    session_memory : unused
        Kept for plugin signature compatibility

    Returns
    -------
    str
        The assistant's response from NVIDIA API
    """
    api_key = parameters.get("api_key")
    prompt = parameters.get("prompt")
    model = parameters.get("model", "minimaxai/minimax-m3")
    temperature = parameters.get("temperature", 1)
    top_p = parameters.get("top_p", 0.95)
    max_tokens = parameters.get("max_tokens", 8192)

    if not api_key or not prompt:
        return "Error: 'api_key' and 'prompt' are required parameters."

    invoke_url = "https://integrate.api.nvidia.com/v1/chat/completions"

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Accept": "application/json",
    }

    payload = {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": prompt
            }
        ],
        "temperature": temperature,
        "top_p": top_p,
        "max_tokens": max_tokens,
        "stream": False
    }

    try:
        response = requests.post(invoke_url, headers=headers, json=payload, timeout=30)
        response.raise_for_status()
        result = response.json()

        # Extract the assistant's message from the response
        if "choices" in result and len(result["choices"]) > 0:
            message = result["choices"][0].get("message", {})
            response_text = message.get("content", "No response received.")
            # Record the API usage
            record_api_usage("nvidia-1")
            return response_text
        else:
            return f"Error: Unexpected response format. {result}"

    except requests.exceptions.RequestException as e:
        return f"Error querying NVIDIA API: {str(e)}"
    except json.JSONDecodeError:
        return "Error: Failed to parse API response as JSON."
    except Exception as e:
        return f"Unexpected error: {str(e)}"
