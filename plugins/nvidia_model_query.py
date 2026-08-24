'''Plugin to query Nvidia LLM models via the existing LLM client.

This plugin allows JARVIS to access Nvidia hosted models such as
`Wan2.2-animate-2-14b` or `nemotron-3.5-lightning-30b-a3b`.
'''\n\nfrom typing import Any, Dict\n\n# Import the generic LLM client used by JARVIS. The client knows how to
# route requests to different providers based on the ``provider`` argument.
# If the implementation changes, adjust the import accordingly.
from core.llm_client import get_response  # type: ignore\n\nPLUGIN = {\n    "name": "nvidia_model_query",\n    "description": "Query an Nvidia LLM model (e.g., Wan2.2-animate-2-14b, nemotron-3.5-lightning-30b-a3b) and obtain a short textual response.",\n    "parameters": {\n        "type": "OBJECT",\n        "properties": {\n            "model": {\n                "type": "string",\n                "description": "Exact name of the Nvidia model to query."
            },\n            "prompt": {\n                "type": "string",\n                "description": "The prompt or question to send to the model."
            },\n            "temperature": {\n                "type": "number",\n                "description": "Sampling temperature (0.0‑1.0).",
                "default": 0.7\n            },\n            "max_output_tokens": {\n                "type": "integer",\n                "description": "Maximum number of tokens to generate.",\n                "default": 512\n            }\n        },\n        "required": ["model", "prompt"]\n    }\n}\n\n\ndef run(parameters: Dict[str, Any], player: Any = None, session_memory: Any = None) -> str:\n    """Execute the plugin.
\n    Parameters\n    ----------\n    parameters: dict\n        Must contain at least ``model`` and ``prompt``. Optional keys are
        ``temperature`` and ``max_output_tokens``.\n    player: optional\n        Unused – part of the generic plugin signature.\n    session_memory: optional\n        Unused – part of the generic plugin signature.\n\n    Returns\n    -------\n    str\n        The model's response or an error message suitable for speaking aloud.\n    """\n    model = parameters.get("model")\n    prompt = parameters.get("prompt")\n    temperature = parameters.get("temperature", 0.7)\n    max_tokens = parameters.get("max_output_tokens", 512)\n\n    if not model or not prompt:\n        return "Error: both 'model' and 'prompt' parameters are required."
\n    try:\n        # The core LLM client abstracts the provider specifics. By passing
        # provider='nvidia' it will route the request to the Nvidia endpoint
        # using the supplied model name.
        response = get_response(\n            provider="nvidia",\n            model=model,\n            prompt=prompt,\n            temperature=temperature,\n            max_output_tokens=max_tokens,\n        )\n        # Ensure we always return a plain string. If the client returns a
        # dict or complex object, attempt to extract a textual field.
        if isinstance(response, dict):\n            # Common keys used by LLM clients.
            for key in ("content", "text", "response", "output"):\n                if key in response:\n                    return str(response[key])\n            return "Error: Unexpected response format from Nvidia model."
        return str(response)\n    except Exception as e:\n        # Never raise – return a user‑friendly message.
        return f"Error while contacting Nvidia model {model}: {e}"\n