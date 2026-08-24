"""NVIDIA Integrate Vision API Plugin

This plugin enables JARVIS to analyze images using NVIDIA's vision models.
Supports image URL analysis and extended thinking for detailed responses.

The plugin requires a Vision-enabled API key from NVIDIA Build.
"""

import json
import requests
from typing import Optional
from core.api_usage import record as record_api_usage


PLUGIN = {
    "name": "nvidia_vision_api",
    "description": "Analyze images using NVIDIA's advanced vision models with extended thinking capability.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "image_url": {
                "type": "string",
                "description": "URL of the image to analyze (e.g., https://example.com/image.jpg)"
            },
            "question": {
                "type": "string",
                "description": "Question or instruction about the image (e.g., 'What is in this image?', 'Describe the objects')"
            },
            "api_key": {
                "type": "string",
                "description": "NVIDIA Vision API key (Bearer token). Optional - uses config if not provided."
            },
            "model": {
                "type": "string",
                "description": "Vision model identifier (default: google/gemma-4-31b-it)",
                "default": "google/gemma-4-31b-it"
            },
            "enable_thinking": {
                "type": "boolean",
                "description": "Enable extended thinking for more detailed analysis (default: true)",
                "default": True
            },
            "max_tokens": {
                "type": "integer",
                "description": "Maximum output tokens (default: 16384)",
                "default": 16384
            },
            "temperature": {
                "type": "number",
                "description": "Sampling temperature 0-2 (default: 1)",
                "default": 1
            },
            "top_p": {
                "type": "number",
                "description": "Top-p sampling 0-1 (default: 0.95)",
                "default": 0.95
            }
        },
        "required": ["image_url", "question"]
    }
}


def run(parameters: dict, player=None, session_memory=None) -> str:
    """Execute NVIDIA Vision API request for image analysis.

    Parameters
    ----------
    parameters : dict
        Must contain 'image_url' and 'question'. Optional: 'api_key', 'model', etc.
    player, session_memory : unused
        Kept for plugin signature compatibility

    Returns
    -------
    str
        The vision model's analysis of the image
    """
    image_url = parameters.get("image_url", "").strip()
    question = parameters.get("question", "").strip()
    api_key = parameters.get("api_key", "").strip()
    model = parameters.get("model", "google/gemma-4-31b-it")
    enable_thinking = parameters.get("enable_thinking", True)
    max_tokens = parameters.get("max_tokens", 16384)
    temperature = parameters.get("temperature", 1)
    top_p = parameters.get("top_p", 0.95)

    if not image_url or not question:
        return "Error: 'image_url' and 'question' are required parameters."

    # Load API key from config if not provided
    if not api_key:
        try:
            from pathlib import Path
            import json
            config_path = Path(__file__).parent.parent / "config" / "api_keys.json"
            with open(config_path) as f:
                config = json.load(f)
            api_key = config.get("nvidia_vision_api_key")
        except Exception:
            pass

    if not api_key:
        return "Error: NVIDIA Vision API key not found in config or parameters."

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
                "content": [
                    {
                        "type": "text",
                        "text": question
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": image_url
                        }
                    }
                ]
            }
        ],
        "max_tokens": max_tokens,
        "temperature": temperature,
        "top_p": top_p,
        "stream": False
    }

    # Add thinking if requested
    if enable_thinking:
        payload["chat_template_kwargs"] = {
            "enable_thinking": True
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
            record_api_usage("nvidia_vision")
            return response_text
        else:
            return f"Error: Unexpected response format. {result}"

    except requests.exceptions.RequestException as e:
        return f"Error querying NVIDIA Vision API: {str(e)}"
    except json.JSONDecodeError:
        return "Error: Failed to parse API response as JSON."
    except Exception as e:
        return f"Unexpected error: {str(e)}"
