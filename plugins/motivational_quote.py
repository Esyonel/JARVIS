import random

PLUGIN = {
    "name": "motivational_quote",
    "description": "Provides a random motivational quote to inspire the user.",
    "parameters": {
        "type": "OBJECT",
        "properties": {},
        "required": []
    }
}

def run(parameters: dict, player=None, session_memory=None) -> str:
    """Return a random motivational quote.

    The function never raises; any unexpected error results in a friendly
    message that can be spoken aloud by JARVIS.
    """
    quotes = [
        "Believe you can and you're halfway there.",
        "The only way to do great work is to love what you do.",
        "Don't watch the clock; do what it does – keep going.",
        "Success is not final, failure is not fatal: it is the courage to continue that counts.",
        "Your limitation—it's only your imagination.",
        "Push yourself, because no one else is going to do it for you.",
        "Great things never come from comfort zones.",
        "Dream it. Wish it. Do it.",
        "Stay focused and never give up.",
        "Believe in yourself and all that you are."
    ]
    try:
        return random.choice(quotes)
    except Exception:
        return "Sorry, I couldn't fetch a motivational quote at the moment."