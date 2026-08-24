'''nvidia_free_endpoint plugin

This plugin allows JARVIS to query NVIDIA's free endpoint API (build.nvidia.com).
It expects an API key (the free "Free Endpoint" key) and a prompt. The model can be
specified; if omitted, it defaults to ``meta/llama-3.1-8b-instruct`` which is
available on the free tier.

The plugin returns the assistant's reply as a short plain string that JARVIS can
speak aloud.
''' 

import json
import requests

PLUGIN = {
    "name": "nvidia_free_endpoint",
    "description": "Use NVIDIA Build free endpoint API key to get AI generated responses.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "api_key": {
                "type": "string",
                "description": "Your NVIDIA free endpoint API key (Bearer token)."
            },
            "prompt": {
                "type": "string",
                "description": "The user prompt to send to the model."
            },
            "model": {
                "type": "string",
                "description": "Model identifier (e.g., 'meta/llama-3.1-8b-instruct'). Optional; defaults to a free tier model."
            }
        },
        "required": ["api_key", "prompt"]
    }
}


def run(parameters: dict, player=None, session_memory=None) -> str:
    """Execute the NVIDIA free endpoint request.

    Parameters
    ----------
    parameters: dict
        Must contain ``api_key`` and ``prompt``. Optional ``model``.
    player, session_memory: unused but kept for plugin signature compatibility.

    Returns
    -------
    str
        The assistant's reply or an error description.
    """
    api_key = parameters.get("api_key", "").strip()
    prompt = parameters.get("prompt", "").strip()
    model = parameters.get("model", "meta/llama-3.1-8b-instruct").strip()

    if not api_key:
        return "NVIDIA API anahtarı eksik. Lütfen geçerli bir Free Endpoint anahtarı sağlayın."
    if not prompt:
        return "İstek metni (prompt) boş. Lütfen bir soru ya da talimat girin."

    url = "https://ai.api.nvidia.com/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Accept": "application/json",
        "Content-Type": "application/json"
    }
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 200,
        "temperature": 0.7,
        "top_p": 0.9
    }

    try:
        response = requests.post(url, headers=headers, data=json.dumps(payload), timeout=30)
        response.raise_for_status()
        data = response.json()
        # Expected shape: {"choices": [{"message": {"content": "..."}}]}
        content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        if not content:
            return "NVIDIA API yanıtı boş geldi."
        # Return trimmed content (single line if possible)
        return content.strip()
    except requests.exceptions.HTTPError as http_err:
        try:
            err_detail = response.json().get("error", {}).get("message", str(http_err))
        except Exception:
            err_detail = str(http_err)
        return f"NVIDIA API hatası: {err_detail}"
    except requests.exceptions.RequestException as req_err:
        return f"NVIDIA API bağlantı hatası: {str(req_err)}"
    except Exception as exc:
        return f"Beklenmeyen bir hata oluştu: {str(exc)}"
