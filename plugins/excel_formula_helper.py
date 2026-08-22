"""
JARVIS plugin — Excel formula helper.

Pure text tool: the user describes what they want a formula to do, Gemini
(via a focused system prompt) returns a ready-to-paste Excel formula plus a
one-line explanation. No file is touched — this is for "what formula do I
use" moments, not for building or editing a spreadsheet.
"""

PLUGIN = {
    "name": "excel_formula_helper",
    "description": (
        "Explains or writes an Excel formula from a plain-language description "
        "— VLOOKUP/XLOOKUP, SUMIF, pivot table steps, conditional formatting "
        "rules, array formulas, etc. Use for: 'şu işi yapan Excel formülünü "
        "yaz', 'iki tabloyu eşleştiren formül ne', 'bu hatayı nasıl düzeltirim "
        "#REF!'. Does not touch any file — pure formula/how-to answer. Use "
        "excel_reader for questions about an existing file's data, and "
        "excel_writer to actually build a spreadsheet file."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "request": {
                "type": "STRING",
                "description": "The user's formula/how-to request, verbatim, in their own language.",
            },
        },
        "required": ["request"],
    },
}


def run(parameters: dict, player=None, session_memory=None) -> str:
    request = (parameters.get("request") or "").strip()
    if not request:
        msg = "Sir, I need to know what you want the formula to do."
        _log(msg, player)
        return msg

    try:
        from config import get_config
        cfg = get_config()
        key = cfg.get("gemini_api_key")
        if not key:
            raise RuntimeError("no Gemini API key configured")

        from google import genai
        client = genai.Client(api_key=key)

        prompt = (
            "You are an Excel formula expert. The user will describe what they "
            "want to do in Excel. Reply with:\n"
            "1) The exact formula, ready to paste (use standard Excel syntax, "
            "comma-separated arguments).\n"
            "2) One short sentence explaining how it works.\n"
            "Keep the whole reply under 80 words, plain text, no markdown "
            "headers. Reply in the same language as the request.\n\n"
            f"Request: {request}"
        )
        resp = client.models.generate_content(model="gemini-flash-latest", contents=prompt)
        answer = (resp.text or "").strip()
        if not answer:
            raise RuntimeError("empty response")
    except Exception as e:
        answer = f"Sir, I couldn't work out the formula right now: {e}"

    _log(answer, player)
    return answer[:2000]


def _log(message: str, player=None) -> None:
    print(f"[ExcelFormulaHelper] {message[:200]}")
    if player:
        try:
            player.write_log(f"JARVIS: {message}")
        except Exception:
            pass
