import os
import traceback
from typing import Dict

# Optional imports – handled gracefully if missing
try:
    import pandas as pd
except Exception:  # pragma: no cover
    pd = None

try:
    import tabula
except Exception:  # pragma: no cover
    tabula = None

try:
    from docx import Document
except Exception:  # pragma: no cover
    Document = None

PLUGIN = {
    "name": "document_processor",
    "description": "Extract tables from PDF, DOCX or plain text files and export them as CSV, JSON or XLSX.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "file_path": {
                "type": "string",
                "description": "Absolute or relative path to the source document (PDF, DOCX, TXT)."
            },
            "output_format": {
                "type": "string",
                "enum": ["csv", "json", "xlsx"],
                "description": "Desired output format for the extracted tables."
            },
            "output_path": {
                "type": "string",
                "description": "Path where the resulting file will be saved. If omitted, a file with the same name as the source and the appropriate extension will be created in the current directory."
            }
        },
        "required": ["file_path", "output_format"]
    }
}


def _extract_from_pdf(path: str) -> pd.DataFrame:
    """Extract the first table from a PDF using tabula.
    Returns a single DataFrame concatenating all found tables.
    """
    if tabula is None:
        raise RuntimeError("tabula-py library is not installed.")
    # tabula returns a list of DataFrames – concatenate them
    tables = tabula.read_pdf(path, pages="all", multiple_tables=True, lattice=True)
    if not tables:
        raise ValueError("No tables found in PDF.")
    return pd.concat(tables, ignore_index=True)


def _extract_from_docx(path: str) -> pd.DataFrame:
    """Extract tables from a DOCX file using python-docx.
    Concatenates all tables into a single DataFrame.
    """
    if Document is None:
        raise RuntimeError("python-docx library is not installed.")
    doc = Document(path)
    all_rows = []
    for table in doc.tables:
        for i, row in enumerate(table.rows):
            cells = [cell.text.strip() for cell in row.cells]
            all_rows.append(cells)
    if not all_rows:
        raise ValueError("No tables found in DOCX.")
    # Use first row as header if it looks like a header (simple heuristic)
    df = pd.DataFrame(all_rows)
    return df


def _extract_from_txt(path: str) -> pd.DataFrame:
    """Attempt to parse a plain‑text file that contains a simple delimited table.
    This is a very naive fallback – it looks for lines containing tabs or commas.
    """
    with open(path, "r", encoding="utf-8") as f:
        lines = [ln.strip() for ln in f if ln.strip()]
    # Determine delimiter by inspecting the first non‑empty line
    delimiter = "\t" if "\t" in lines[0] else ","
    rows = [ln.split(delimiter) for ln in lines]
    return pd.DataFrame(rows)


def _save_dataframe(df: "pd.DataFrame", fmt: str, out_path: str) -> None:
    """Save DataFrame in the requested format."""
    if fmt == "csv":
        df.to_csv(out_path, index=False)
    elif fmt == "json":
        df.to_json(out_path, orient="records", force_ascii=False, indent=2)
    elif fmt == "xlsx":
        df.to_excel(out_path, index=False, engine="openpyxl")
    else:
        raise ValueError(f"Unsupported format: {fmt}")


def run(parameters: Dict, player=None, session_memory=None) -> str:
    """Entry point for the plugin.
    Returns a short spoken message indicating success or error.
    """
    try:
        if pd is None:
            return "I cannot process documents because pandas is not installed."
        file_path = parameters.get("file_path")
        output_format = parameters.get("output_format", "csv").lower()
        output_path = parameters.get("output_path")

        if not file_path:
            return "Please provide a file path to process."
        if not os.path.isfile(file_path):
            return f"The file {file_path} does not exist."

        ext = os.path.splitext(file_path)[1].lower()
        if ext == ".pdf":
            df = _extract_from_pdf(file_path)
        elif ext == ".docx":
            df = _extract_from_docx(file_path)
        elif ext in {".txt", ".csv"}:
            df = _extract_from_txt(file_path)
        else:
            return f"Unsupported file type: {ext}. Supported types are PDF, DOCX and plain text."

        if not output_path:
            base = os.path.splitext(os.path.basename(file_path))[0]
            output_path = f"{base}_extracted.{output_format}"

        _save_dataframe(df, output_format, output_path)
        return f"Document processed successfully. The data has been saved to {output_path}."
    except Exception as e:
        # Log traceback for debugging (if a logger is available)
        tb = traceback.format_exc()
        # In a real environment we might log tb, but for the spoken response keep it short
        return f"An error occurred while processing the document: {str(e)}"
