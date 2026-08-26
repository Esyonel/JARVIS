"""
JARVIS plugin — deterministic table extraction from PDF/DOCX/plain-text into
CSV/JSON/XLSX (tabula/python-docx/pandas — no LLM involved, so numbers and
cell values come out exactly as they were in the source).

For messier, less-structured content that needs an LLM to make sense of it,
use document_extractor instead. For a scanned/photographed document with no
selectable text layer, use document_ocr.

(This file used to have two near-duplicate siblings — document_processing.py
and document_processing_template.py — independently reinvented by JARVIS's
own daily self-evolution run because it didn't recognize it already had this
capability under a different name. This version merges the best parts of all
three: automatic source-type detection from the file extension, robust Path-
based path handling, and one worksheet per table in the XLSX output.)
"""

import json
import os
from pathlib import Path
from typing import List

import pandas as pd

PLUGIN = {
    "name": "document_processor",
    "description": (
        "Extracts tables from a PDF, DOCX, or plain-text/CSV file and saves them "
        "as CSV, JSON, or XLSX — reads cell values directly (tabula/python-docx), "
        "no AI involved, so numbers come out exact. Use for well-structured "
        "documents with real tables. For messy/unstructured content, use "
        "document_extractor instead; for a scanned image with no text layer, use "
        "document_ocr."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "file_path": {
                "type": "STRING",
                "description": "Absolute or relative path to the source document (PDF, DOCX, or TXT/CSV).",
            },
            "output_format": {
                "type": "STRING",
                "enum": ["csv", "json", "xlsx"],
                "description": "Desired output format for the extracted tables.",
            },
            "output_path": {
                "type": "STRING",
                "description": "Optional path where the result will be saved. If omitted, saved next to the source with the appropriate extension.",
            },
        },
        "required": ["file_path", "output_format"],
    },
}


def _extract_tables_from_pdf(file_path: Path) -> List[pd.DataFrame]:
    try:
        import tabula
    except Exception:
        return []
    try:
        tables = tabula.read_pdf(
            str(file_path),
            pages="all",
            multiple_tables=True,
            pandas_options={"dtype": str},
        )
        return tables if isinstance(tables, list) else []
    except Exception:
        return []


def _extract_tables_from_docx(file_path: Path) -> List[pd.DataFrame]:
    try:
        from docx import Document
    except Exception:
        return []
    try:
        doc = Document(str(file_path))
        tables = []
        for table in doc.tables:
            data = [[cell.text.strip() for cell in row.cells] for row in table.rows]
            if data:
                tables.append(pd.DataFrame(data))
        return tables
    except Exception:
        return []


def _extract_tables_from_txt(file_path: Path) -> List[pd.DataFrame]:
    """Naive delimited-table detection for plain text/CSV files."""
    try:
        lines = [
            ln
            for ln in file_path.read_text(encoding="utf-8").splitlines()
            if ln.strip()
        ]
        if not lines:
            return []
        delimiter = (
            "\t"
            if "\t" in lines[0]
            else ("," if "," in lines[0] else ";" if ";" in lines[0] else None)
        )
        if not delimiter:
            return []
        rows = [ln.split(delimiter) for ln in lines]
        return [pd.DataFrame(rows)]
    except Exception:
        return []


def _save_tables(
    tables: List[pd.DataFrame], output_format: str, output_path: Path
) -> None:
    if not tables:
        raise ValueError("No tables were extracted to save.")

    if output_format == "csv":
        pd.concat(tables, ignore_index=True).to_csv(
            output_path, index=False, encoding="utf-8"
        )
    elif output_format == "json":
        all_records = [df.to_dict(orient="records") for df in tables]
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(all_records, f, ensure_ascii=False, indent=2)
    elif output_format == "xlsx":
        with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
            for idx, df in enumerate(tables, start=1):
                df.to_excel(writer, sheet_name=f"Table{idx}", index=False)
    else:
        raise ValueError(f"Unsupported output format: {output_format}")


def run(parameters: dict, player=None, session_memory=None) -> str:
    try:
        file_path = Path(parameters.get("file_path", "")).expanduser().resolve()
        if not file_path.is_file():
            return f"I couldn't find the file {file_path}. Please check the path and try again."

        output_format = (parameters.get("output_format") or "").lower()
        if output_format not in {"csv", "json", "xlsx"}:
            return "The output format must be csv, json, or xlsx."

        output_path_str = parameters.get("output_path")
        output_path = (
            Path(output_path_str).expanduser().resolve()
            if output_path_str
            else file_path.with_suffix("." + output_format)
        )
        os.makedirs(output_path.parent, exist_ok=True)

        ext = file_path.suffix.lower()
        if ext == ".pdf":
            tables = _extract_tables_from_pdf(file_path)
        elif ext in {".docx", ".doc"}:
            tables = _extract_tables_from_docx(file_path)
        elif ext in {".txt", ".csv"}:
            tables = _extract_tables_from_txt(file_path)
        else:
            return f"Unsupported file type {ext}. I can process PDF, DOCX, and plain text/CSV files."

        if not tables:
            return "I couldn't detect any tables in the document. Make sure it contains recognizable tables."

        _save_tables(tables, output_format, output_path)
        return f"The document has been processed successfully. The data was saved to {output_path.name}."
    except Exception as e:
        return f"An error occurred while processing the document: {e}"
