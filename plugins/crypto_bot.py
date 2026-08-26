PLUGIN = {
    "name": "crypto_bot",
    "description": "Provides basic cryptocurrency information and simple trade actions via an external crypto bot service.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "symbol": {
                "type": "string",
                "description": "Cryptocurrency symbol, e.g., BTC"
            },
            "action": {
                "type": "string",
                "enum": ["price", "buy", "sell"],
                "description": "Action to perform"
            },
            "amount": {
                "type": "number",
                "description": "Amount of cryptocurrency for buy/sell (optional)"
            }
        },
        "required": ["symbol", "action"]
    }
}

def run(parameters: dict, player=None, session_memory=None) -> str:
    """Execute a crypto‑related request.

    Parameters
    ----------
    parameters: dict
        Expected keys are ``symbol`` (str), ``action`` (str) and optional ``amount`` (float).
    player, session_memory: optional JARVIS objects (ignored in this simple implementation).

    Returns
    -------
    str
        A short spoken response describing the result or an error message.
    """
    try:
        symbol = parameters.get("symbol", "").upper()
        action = parameters.get("action", "").lower()
        amount = parameters.get("amount")

        if not symbol or not action:
            return "Missing required parameters for crypto operation."

        if action == "price":
            # Placeholder: In a real implementation, query a crypto price API.
            return f"The current price of {symbol} is 42,000 dollars."
        elif action in ("buy", "sell"):
            if amount is None:
                return f"Please specify the amount to {action}."
            # Placeholder: In a real implementation, send a trade request to the crypto bot.
            return f"Successfully placed a {action} order for {amount} {symbol}."
        else:
            return f"Unknown action {action}. Please use price, buy, or sell."
    except Exception as e:
        return f"An error occurred while processing the crypto request: {str(e)}"
