import os
import json
from pathlib import Path
from typing import List

import pandas as pd

# Optional imports – they may not be installed in every environment.
# We import lazily inside functions and handle ImportError gracefully.

PLUGIN = {
    "name": "document_processing_template",
    "description": "Extract tables from PDF, DOCX or plain text documents and convert them to CSV, JSON, or XLSX.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "file_path": {
                "type": "string",
                "description": "Absolute or relative path to the source document (PDF, DOCX, or TXT)."
            },
            "output_format": {
                "type": "string",
                "description": "Desired output format: 'csv', 'json', or 'xlsx'.",
                "enum": ["csv", "json", "xlsx"]
            },
            "output_path": {
                "type": "string",
                "description": "Optional full path where the result will be saved. If omitted, the file will be saved next to the source with an appropriate extension."
            }
        },
        "required": ["file_path", "output_format"]
    }
}


def _extract_tables_from_pdf(file_path: Path) -> List[pd.DataFrame]:
    """Extract tables from a PDF using tabula-py.
    Returns a list of DataFrames. If tabula-py is not available, returns an empty list.
    """
    try:
        import tabula
    except Exception as e:
        return []
    try:
        # read_pdf returns a list of DataFrames when multiple_tables=True
        tables = tabula.read_pdf(str(file_path), pages="all", multiple_tables=True, pandas_options={"dtype": str})
        return tables if isinstance(tables, list) else []
    except Exception:
        return []


def _extract_tables_from_docx(file_path: Path) -> List[pd.DataFrame]:
    """Extract tables from a DOCX file using python-docx.
    Returns a list of DataFrames.
    """
    try:
        from docx import Document
    except Exception:
        return []
    try:
        doc = Document(str(file_path))
        tables = []
        for table in doc.tables:
            data = []
            for row in table.rows:
                data.append([cell.text.strip() for cell in row.cells])
            if data:
                df = pd.DataFrame(data)
                tables.append(df)
        return tables
    except Exception:
        return []


def _extract_tables_from_txt(file_path: Path) -> List[pd.DataFrame]:
    """Very naive extraction from plain text – attempts to parse CSV‑like rows.
    Returns a single DataFrame if a table‑like structure is detected, otherwise empty list.
    """
    try:
        lines = file_path.read_text(encoding="utf-8").splitlines()
        # Detect lines containing at least two delimiters (comma, tab, or semicolon)
        delimiter = None
        for line in lines:
            if "," in line:
                delimiter = ","
                break
            if "\t" in line:
                delimiter = "\t"
                break
            if ";" in line:
                delimiter = ";"
                break
        if not delimiter:
            return []
        rows = [l.split(delimiter) for l in lines if delimiter in l]
        df = pd.DataFrame(rows)
        return [df]
    except Exception:
        return []


def _save_tables(tables: List[pd.DataFrame], output_format: str, output_path: Path) -> None:
    """Save extracted tables according to the requested format.
    - CSV: all tables concatenated vertically.
    - JSON: list of tables, each as a list of records.
    - XLSX: each table on a separate worksheet (Table1, Table2, ...).
    """
    if not tables:
        raise ValueError("No tables were extracted to save.")

    if output_format == "csv":
        # Concatenate with a blank row between tables for readability.
        concatenated = pd.concat(tables, ignore_index=True)
        concatenated.to_csv(output_path, index=False, encoding="utf-8")
    elif output_format == "json":
        all_records = [df.to_dict(orient="records") for df in tables]
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(all_records, f, ensure_ascii=False, indent=2)
    elif output_format == "xlsx":
        with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
            for idx, df in enumerate(tables, start=1):
                sheet_name = f"Table{idx}"
                df.to_excel(writer, sheet_name=sheet_name, index=False)
    else:
        raise ValueError(f"Unsupported output format: {output_format}")


def run(parameters: dict, player=None, session_memory=None) -> str:
    """Entry point for the JARVIS plugin.
    Expected parameters:
        file_path (str): Path to the source document.
        output_format (str): One of 'csv', 'json', 'xlsx'.
        output_path (str, optional): Destination file path.
    Returns a short spoken message.
    """
    try:
        file_path = Path(parameters.get("file_path", "")).expanduser().resolve()
        if not file_path.is_file():
            return f"I couldn't find the file {file_path}. Please check the path and try again."

        output_format = parameters.get("output_format", "").lower()
        if output_format not in {"csv", "json", "xlsx"}:
            return "The output format must be csv, json, or xlsx."

        # Determine default output path if not supplied
        output_path_str = parameters.get("output_path")
        if output_path_str:
            output_path = Path(output_path_str).expanduser().resolve()
        else:
            suffix = "." + output_format
            output_path = file_path.with_suffix(suffix)

        # Extract tables based on file extension
        ext = file_path.suffix.lower()
        tables: List[pd.DataFrame] = []
        if ext == ".pdf":
            tables = _extract_tables_from_pdf(file_path)
        elif ext in {".docx", ".doc"}:
            tables = _extract_tables_from_docx(file_path)
        elif ext in {".txt", ".csv"}:
            tables = _extract_tables_from_txt(file_path)
        else:
            return f"Unsupported file type {ext}. I can process PDF, DOCX, and plain text files."

        if not tables:
            return "I couldn't detect any tables in the document. Make sure the document contains recognizable tables."

        # Save the extracted tables
        _save_tables(tables, output_format, output_path)
        return f"The document has been processed successfully. The data was saved to {output_path.name}."
    except Exception as e:
        # Log the exception internally if a logging system exists; otherwise, just return a friendly message.
        return f"An error occurred while processing the document: {str(e)}"
