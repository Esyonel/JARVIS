PLUGIN = {
    "name": "self_improvement_program",
    "description": "Generates a short self‑improvement program for personal development.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "goal": {
                "type": "STRING",
                "description": "The main self‑improvement goal, e.g., productivity, health, learning."
            },
            "duration_days": {
                "type": "INTEGER",
                "description": "Number of days for the program (1‑30)."
            }
        },
        "required": []
    }
}


def run(parameters: dict, player=None, session_memory=None) -> str:
    """Return a concise spoken self‑improvement program.

    Parameters
    ----------
    parameters: dict
        May contain "goal" (str) and "duration_days" (int).
    player, session_memory: optional, ignored for this plugin.

    Returns
    -------
    str
        A short plain‑text description of the program.
    """
    try:
        goal = parameters.get("goal", "general development").strip()
        duration = parameters.get("duration_days", 7)
        # Validate duration
        if not isinstance(duration, int) or duration < 1:
            duration = 7
        if duration > 30:
            duration = 30

        # Simple predefined activities based on goal keywords
        goal_lower = goal.lower()
        activities = []
        if "productivity" in goal_lower:
            activities = ["morning planning", "focus blocks", "daily review"]
        elif "health" in goal_lower or "fitness" in goal_lower:
            activities = ["30‑minute walk", "stretching", "balanced meals"]
        elif "learning" in goal_lower or "skill" in goal_lower:
            activities = ["read a chapter", "practice the skill for 30 min", "summarize what you learned"]
        else:
            activities = ["meditation", "read a chapter", "light exercise"]

        # Build a short sentence
        act_str = ", ".join(activities)
        result = f"Your {duration}-day self‑improvement program focusing on {goal} includes: {act_str}."
        return result
    except Exception as e:
        # Return a friendly error message without raising
        return f"Sorry, I couldn't create the self‑improvement program. {e}"