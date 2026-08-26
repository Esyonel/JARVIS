"""Shared Tesseract OCR helpers for JARVIS plugins (document_ocr, document_extractor).

Bundles a self-contained tessdata directory (JARVIS/resources/tessdata) with
Turkish + English + orientation data, so OCR works out of the box regardless
of what language packs happen to be installed system-wide (installing into
Program Files needs admin rights; pointing TESSDATA_PREFIX at our own copy
doesn't).
"""

import os
from pathlib import Path

_RESOURCES_TESSDATA = Path(__file__).resolve().parent.parent / "resources" / "tessdata"

_WINDOWS_TESSERACT_FALLBACK_PATHS = [
    r"C:\Program Files\Tesseract-OCR\tesseract.exe",
    r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
]

MIN_TEXT_LAYER_CHARS = 20


def ensure_tesseract_ready() -> tuple[bool, str]:
    """Point pytesseract at a working tesseract.exe + bundled tessdata.

    Returns (ready, error_message_in_turkish).
    """
    try:
        import pytesseract
    except ImportError:
        return False, "pytesseract kütüphanesi kurulu değil."

    if _RESOURCES_TESSDATA.is_dir():
        os.environ["TESSDATA_PREFIX"] = str(_RESOURCES_TESSDATA)

    try:
        pytesseract.get_tesseract_version()
        return True, ""
    except Exception:
        pass

    for candidate in _WINDOWS_TESSERACT_FALLBACK_PATHS:
        if Path(candidate).is_file():
            pytesseract.pytesseract.tesseract_cmd = candidate
            try:
                pytesseract.get_tesseract_version()
                return True, ""
            except Exception:
                continue

    return False, (
        "Tesseract OCR motoru sistemde kurulu değil (pytesseract sadece bir "
        "köprü, asıl motor ayrı kurulmalı). Windows'ta: "
        "https://github.com/UB-Mannheim/tesseract/wiki adresinden kurup, "
        "kurulum dizinini PATH'e eklemen gerekiyor."
    )


def page_has_text_layer(page) -> bool:
    """page: a pymupdf Page object."""
    return len(page.get_text("text").strip()) >= MIN_TEXT_LAYER_CHARS


def extract_pdf_pages(path, language: str = "tur+eng", dpi: int = 300, log=None) -> list[str]:
    """Return per-page text: real text layer where present, OCR otherwise.

    Requires ensure_tesseract_ready() to have succeeded if any page needs OCR.
    """
    import pymupdf as fitz
    import pytesseract
    from PIL import Image

    doc = fitz.open(path)
    zoom = dpi / 72
    matrix = fitz.Matrix(zoom, zoom)
    pages_text: list[str] = []
    try:
        for i, page in enumerate(doc, start=1):
            if page_has_text_layer(page):
                pages_text.append(page.get_text("text"))
                if log:
                    log(f"Sayfa {i}/{doc.page_count}: metin katmani")
                continue
            pix = page.get_pixmap(matrix=matrix)
            img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
            pages_text.append(pytesseract.image_to_string(img, lang=language))
            if log:
                log(f"Sayfa {i}/{doc.page_count}: OCR")
    finally:
        doc.close()
    return pages_text


def extract_pdf_tables(path) -> list[list[list[str]]]:
    """Best-effort table extraction from PDF pages that have a text layer.

    Scanned pages have no detectable tables this way (no text layer to
    analyze) -- for those, the OCR'd text in extract_pdf_pages() is the
    fallback source of data.
    """
    import pymupdf as fitz

    doc = fitz.open(path)
    tables: list[list[list[str]]] = []
    try:
        for page in doc:
            if not page_has_text_layer(page):
                continue
            for table in page.find_tables().tables:
                tables.append(table.extract())
    finally:
        doc.close()
    return tables
