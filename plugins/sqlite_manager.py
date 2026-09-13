PLUGIN = {
    "name": "sqlite_manager",
    "description": "Executes SQL queries on a local SQLite database and returns the results in a table format.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "database_path": {
                "type": "string",
                "description": "Full path to the .sqlite or .db file."
            },
            "query": {
                "type": "string",
                "description": "SQL query to execute (SELECT statements are supported)."
            }
        },
        "required": ["database_path", "query"]
    }
}


def run(parameters: dict, player=None, session_memory=None) -> str:
    """Execute an SQLite query and return results as a formatted table.

    Parameters
    ----------
    parameters: dict
        Must contain "database_path" and "query" keys.
    player: optional
        Not used but kept for plugin signature compatibility.
    session_memory: optional
        Not used but kept for plugin signature compatibility.

    Returns
    -------
    str
        Human‑readable string with query results or an error description.
    """
    import os
    import sqlite3

    db_path = parameters.get("database_path")
    query = parameters.get("query")

    if not db_path or not query:
        return "Error: 'database_path' and 'query' parameters are required."

    if not os.path.isfile(db_path):
        return f"Error: The database file '{db_path}' does not exist."

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute(query)
        rows = cursor.fetchall()
        columns = [desc[0] for desc in cursor.description] if cursor.description else []
        conn.close()
    except Exception as e:
        return f"Error executing query: {e}"

    if not rows:
        return "Query executed successfully but returned no results."

    # Determine column widths for pretty printing
    col_widths = []
    for i, col in enumerate(columns):
        max_width = len(str(col))
        for row in rows:
            max_width = max(max_width, len(str(row[i])))
        col_widths.append(max_width)

    # Build header
    header = " | ".join(str(col).ljust(col_widths[i]) for i, col in enumerate(columns))
    separator = "-+-".join("-" * w for w in col_widths)
    # Build rows
    data_lines = []
    for row in rows:
        line = " | ".join(str(row[i]).ljust(col_widths[i]) for i in range(len(columns)))
        data_lines.append(line)
    result = "\n".join([header, separator] + data_lines)
    return result
