PLUGIN = {
    "name": "daily_joke",
    "description": "Provides a random joke to lighten the mood.",
    "parameters": {
        "type": "OBJECT",
        "properties": {},
        "required": []
    }
}

import random

_JOKES = [
    "Why don't scientists trust atoms? Because they make up everything!",
    "I told my computer I needed a break, and it said 'No problem – I’ll go to sleep.'",
    "Why did the scarecrow win an award? Because he was outstanding in his field!",
    "I would tell you a UDP joke, but you might not get it.",
    "Why do programmers prefer dark mode? Because light attracts bugs.",
    "Why was the math book sad? Because it had too many problems.",
    "I asked my phone why it was sad. It said, 'I have low battery anxiety.'"
]

def run(parameters: dict, player=None, session_memory=None) -> str:
    """Return a random joke.

    Parameters
    ----------
    parameters: dict
        Currently unused, kept for compatibility with the plugin system.
    player: optional
        Unused – placeholder for audio playback if needed.
    session_memory: optional
        Unused – placeholder for accessing session-specific data.
    """
    try:
        joke = random.choice(_JOKES)
        return joke
    except Exception as e:
        return f"Üzgünüm, bir hata oluştu: {e}"