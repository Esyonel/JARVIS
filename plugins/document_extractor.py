import os
import json
import csv
from pathlib import Path

# Attempt to import optional heavy libraries; if unavailable, we will handle gracefully.
try:
    import pdfplumber
except Exception:
    pdfplumber = None

try:
    import docx
except Exception:
    docx = None

try:
    import pandas as pd
except Exception:
    pd = None

# Core JARVIS utilities – these imports follow the existing project conventions.
from core.ai_text import get_ai_response  # assumed helper that talks to Gemini/LLaMA etc.

PLUGIN = {
    "name": "document_extractor",
    "description": "Extracts data from unstructured text, PDF, or DOCX files (including tables) and converts it into a structured format such as CSV, JSON, or XLSX using AI prompts.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "file_path": {
                "type": "STRING",
                "description": "Absolute or relative path to the source document (txt, pdf, or docx)."
            },
            "output_format": {
                "type": "STRING",
                "enum": ["csv", "json", "xlsx"],
                "description": "Desired output format for the extracted data."
            },
            "prompt": {
                "type": "STRING",
                "description": "Optional custom prompt to guide the AI on how to structure the extracted data."
            }
        },
        "required": ["file_path", "output_format"]
    }
}

def _extract_text_from_pdf(path: Path) -> str:
    if not pdfplumber:
        raise RuntimeError("pdfplumber library is not installed.")
    text = []
    with pdfplumber.open(str(path)) as pdf:
        for page in pdf.pages:
            text.append(page.extract_text() or "")
    return "\n".join(text)

def _extract_text_from_docx(path: Path) -> str:
    if not docx:
        raise RuntimeError("python-docx library is not installed.")
    doc = docx.Document(str(path))
    paragraphs = [p.text for p in doc.paragraphs]
    return "\n".join(paragraphs)

def _extract_tables_from_docx(path: Path):
    if not docx:
        raise RuntimeError("python-docx library is not installed.")
    doc = docx.Document(str(path))
    tables = []
    for table in doc.tables:
        data = []
        for row in table.rows:
            data.append([cell.text for cell in row.cells])
        tables.append(data)
    return tables

def _extract_tables_from_pdf(path: Path):
    if not pdfplumber:
        raise RuntimeError("pdfplumber library is not installed.")
    tables = []
    with pdfplumber.open(str(path)) as pdf:
        for page in pdf.pages:
            for tbl in page.extract_tables():
                tables.append(tbl)
    return tables

def _format_output(data, fmt: str, base_name: str) -> str:
    """Write *data* to a file in the requested *fmt*.
    Returns the path of the written file.
    """
    output_path = Path(f"{base_name}.{fmt}")
    try:
        if fmt == "json":
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        elif fmt == "csv":
            # Expect *data* to be a list of rows (list of lists).
            with open(output_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                for row in data:
                    writer.writerow(row)
        elif fmt == "xlsx":
            if not pd:
                raise RuntimeError("pandas is required for XLSX output but is not installed.")
            df = pd.DataFrame(data[1:], columns=data[0] if data else None)
            df.to_excel(output_path, index=False)
        else:
            raise ValueError(f"Unsupported format: {fmt}")
    except Exception as e:
        raise RuntimeError(f"Failed to write output file: {e}")
    return str(output_path)

def run(parameters: dict, player=None, session_memory=None) -> str:
    """Entry point for the JARVIS plugin system.

    Parameters
    ----------
    parameters: dict
        Must contain ``file_path`` and ``output_format``. ``prompt`` is optional.
    player, session_memory: optional JARVIS objects (ignored here).

    Returns
    -------
    str
        A short spoken response indicating success or the error that occurred.
    """
    try:
        file_path = parameters.get("file_path")
        output_format = parameters.get("output_format").lower()
        custom_prompt = parameters.get("prompt")

        if not file_path:
            return "Belirttiğiniz dosya yolu eksik. Lütfen bir dosya yolu sağlayın."
        if output_format not in {"csv", "json", "xlsx"}:
            return f"Desteklenmeyen çıktı formatı: {output_format}. Lütfen csv, json veya xlsx seçin."

        path = Path(file_path).expanduser().resolve()
        if not path.is_file():
            return f"Dosya bulunamadı: {file_path}. Lütfen yolu kontrol edin."

        # Determine extraction method based on extension.
        ext = path.suffix.lower()
        raw_text = ""
        tables = []
        if ext == ".txt":
            raw_text = path.read_text(encoding="utf-8")
        elif ext == ".pdf":
            raw_text = _extract_text_from_pdf(path)
            tables = _extract_tables_from_pdf(path)
        elif ext == ".docx":
            raw_text = _extract_text_from_docx(path)
            tables = _extract_tables_from_docx(path)
        else:
            return f"Dosya uzantısı {ext} desteklenmiyor. Sadece txt, pdf ve docx dosyaları işlenebilir."

        # Build prompt for AI – if a custom one is supplied, use it; otherwise, a generic one.
        if custom_prompt:
            prompt = custom_prompt
        else:
            prompt = (
                "Aşağıdaki belge içeriğini ve varsa tabloları analiz edip, "
                f"verileri {output_format.upper()} formatına dönüştür. "
                "Sonuç sadece veri kısmını içermeli, ek açıklama olmamalı."
            )
        # Combine raw text and tables into a single string for the model.
        content_for_ai = raw_text
        if tables:
            content_for_ai += "\n\nTablolar:\n"
            for idx, tbl in enumerate(tables, start=1):
                content_for_ai += f"Tablo {idx}:\n"
                for row in tbl:
                    content_for_ai += ", ".join(row) + "\n"
                content_for_ai += "\n"

        # Ask the LLM to produce structured data.
        ai_response = get_ai_response(prompt, content_for_ai)
        # The AI is expected to return JSON or CSV string depending on format.
        # We'll attempt to parse JSON when needed.
        structured_data = None
        if output_format == "json":
            try:
                structured_data = json.loads(ai_response)
            except Exception:
                # Fallback: treat raw response as string and wrap.
                structured_data = {"result": ai_response}
        elif output_format in {"csv", "xlsx"}:
            # Assume CSV rows separated by newlines.
            rows = [line.split(",") for line in ai_response.strip().splitlines()]
            structured_data = rows
        else:
            structured_data = ai_response

        base_name = path.stem + "_extracted"
        output_file = _format_output(structured_data, output_format, base_name)
        return f"Belge başarıyla işlendi ve {output_format.upper()} dosyası olarak kaydedildi: {output_file}."
    except Exception as exc:
        # Log could be added here; for now, we just return a friendly message.
        return f"Belge işleme sırasında bir hata oluştu: {str(exc)}"
