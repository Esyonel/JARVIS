import random

# Define the plugin metadata according to the JARVIS plugin contract
PLUGIN = {
    "name": "random_fact",
    "description": "Provides a random interesting fact to the user.",
    "parameters": {
        "type": "OBJECT",
        "properties": {},
        "required": []
    }
}

# A small static list of fun facts. This avoids external network calls and keeps the plugin reliable.
_FACTS = [
    "Honey never spoils. Archaeologists have found edible honey in ancient Egyptian tombs.",
    "Octopuses have three hearts.",
    "Bananas are berries, but strawberries aren't.",
    "A day on Venus is longer than a year on Venus.",
    "Wombat poop is cube‑shaped.",
    "There are more possible iterations of a game of chess than atoms in the observable universe.",
    "The Eiffel Tower can be 15 cm taller during hot days due to thermal expansion.",
    "Humans share 60% of their DNA with bananas.",
    "The first computer bug was an actual moth stuck in a Harvard Mark II computer in 1947.",
    "A single bolt of lightning contains enough energy to toast 100,000 slices of bread."
]

def run(parameters: dict, player=None, session_memory=None) -> str:
    """Return a random fact.

    Parameters
    ----------
    parameters: dict
        Currently unused; present for interface compatibility.
    player: optional
        Optional audio player object; not used here.
    session_memory: optional
        Optional memory object; not used here.

    Returns
    -------
    str
        A short plain‑text fact that JARVIS can speak aloud.
    """
    try:
        fact = random.choice(_FACTS)
        return fact
    except Exception as e:
        # In case something unexpected happens, return a friendly error message.
        return f"Üzgünüm, bir hata oluştu ve bir bilgi getirilemedi: {e}"