PLUGIN = {
    "name": "document_processing",
    "description": "Extract tables from PDF, DOCX, or plain text and convert them to CSV, JSON, or XLSX.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "file_path": {
                "type": "STRING",
                "description": "Absolute path to the source document."
            },
            "source_type": {
                "type": "STRING",
                "enum": ["pdf", "docx", "text"],
                "description": "Type of the source document."
            },
            "output_format": {
                "type": "STRING",
                "enum": ["csv", "json", "xlsx"],
                "description": "Desired output format."
            },
            "output_path": {
                "type": "STRING",
                "description": "Absolute path where the result will be saved."
            }
        },
        "required": ["file_path", "source_type", "output_format", "output_path"]
    }
}

def run(parameters: dict, player=None, session_memory=None) -> str:
    """Extract tables from a document and save them in the requested format.

    The function catches all errors and returns a short plain‑text message that
    can be spoken by the voice assistant.
    """
    import os
    try:
        file_path = parameters.get("file_path")
        source_type = parameters.get("source_type")
        output_format = parameters.get("output_format")
        output_path = parameters.get("output_path")

        if not all([file_path, source_type, output_format, output_path]):
            return "Missing required parameters for document processing."

        if not os.path.isfile(file_path):
            return f"File not found: {file_path}"

        # Ensure output directory exists
        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        # ------------------------------------------------------------------
        # 1️⃣ Load tables from the source document
        # ------------------------------------------------------------------
        if source_type == "pdf":
            try:
                import tabula
                dfs = tabula.read_pdf(file_path, pages="all", multiple_tables=True)
            except Exception as e:
                return f"Failed to extract tables from PDF: {e}"
        elif source_type == "docx":
            try:
                from docx import Document
                import pandas as pd
                doc = Document(file_path)
                dfs = []
                for table in doc.tables:
                    data = [[cell.text for cell in row.cells] for row in table.rows]
                    dfs.append(pd.DataFrame(data))
            except Exception as e:
                return f"Failed to extract tables from DOCX: {e}"
        elif source_type == "text":
            try:
                import pandas as pd
                # Attempt to read as CSV/TSV; let pandas infer the separator
                df = pd.read_csv(file_path, sep=None, engine="python")
                dfs = [df]
            except Exception as e:
                return f"Failed to read text file as table: {e}"
        else:
            return f"Unsupported source_type: {source_type}"

        if not dfs:
            return "No tables found in the document."

        # ------------------------------------------------------------------
        # 2️⃣ Combine tables (if more than one) into a single DataFrame
        # ------------------------------------------------------------------
        try:
            import pandas as pd
            combined = pd.concat(dfs, ignore_index=True)
        except Exception as e:
            return f"Error combining tables: {e}"

        # ------------------------------------------------------------------
        # 3️⃣ Save the result in the requested format
        # ------------------------------------------------------------------
        try:
            if output_format == "csv":
                combined.to_csv(output_path, index=False)
            elif output_format == "json":
                combined.to_json(output_path, orient="records", force_ascii=False, lines=True)
            elif output_format == "xlsx":
                combined.to_excel(output_path, index=False, engine="openpyxl")
            else:
                return f"Unsupported output_format: {output_format}"
        except Exception as e:
            return f"Failed to write output file: {e}"

        return f"Document processed successfully. Output saved to {output_path}."
    except Exception as exc:
        return f"An unexpected error occurred during document processing: {exc}"
