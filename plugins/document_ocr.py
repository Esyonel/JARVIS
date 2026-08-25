"""
JARVIS plugin — OCR text extraction for scanned/photographed documents.

document_extractor / document_processing / document_processor all assume the
source PDF or DOCX already contains a text layer (they read it directly).
None of them can handle a PDF that is really just scanned page images, or a
phone photo of a paper document — that's what this plugin is for: it renders
each page to an image (PyMuPDF) and runs Tesseract OCR (pytesseract) over it.

Requires the Tesseract OCR engine to be installed on the system (not just the
pytesseract Python wrapper) — pytesseract only calls out to the `tesseract`
executable, it doesn't ship it. If it's missing, run() returns a clear
Turkish instruction instead of a stack trace.
"""

from pathlib import Path

PLUGIN = {
    "name": "document_ocr",
    "description": (
        "Extracts text from a SCANNED or PHOTOGRAPHED document — an image "
        "file (jpg/png) or a PDF made of page scans with no selectable text. "
        "Use for: 'bu taranmış evrakı oku', 'fotoğrafını çektiğim belgeyi "
        "metne çevir', 'OCR yap'. Do NOT use for a normal text-based PDF or "
        "DOCX — use document_extractor for those instead, it's faster and "
        "more accurate since it reads the text layer directly."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "file_path": {
                "type": "STRING",
                "description": "Absolute or relative path to the scanned PDF or image file.",
            },
            "language": {
                "type": "STRING",
                "description": (
                    "Tesseract language code(s), e.g. 'tur', 'eng', or 'tur+eng' "
                    "for mixed Turkish/English pages. Defaults to 'tur+eng'."
                ),
            },
            "output_path": {
                "type": "STRING",
                "description": (
                    "Optional path to save the extracted text as .txt. If omitted, "
                    "saved next to the source file as '<name>_ocr.txt'."
                ),
            },
        },
        "required": ["file_path"],
    },
}

_IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".tif", ".webp"}
_RENDER_DPI = 300


_WINDOWS_FALLBACK_PATHS = [
    r"C:\Program Files\Tesseract-OCR\tesseract.exe",
    r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
]


def _tesseract_ready() -> tuple[bool, str]:
    try:
        import pytesseract
    except ImportError:
        return False, "pytesseract kütüphanesi kurulu değil."
    try:
        pytesseract.get_tesseract_version()
        return True, ""
    except Exception:
        pass

    # Installed (e.g. via winget) but not on PATH — try the known install dirs
    # directly rather than requiring a machine-wide PATH edit.
    for candidate in _WINDOWS_FALLBACK_PATHS:
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


def _ocr_image(image, language: str) -> str:
    import pytesseract
    return pytesseract.image_to_string(image, lang=language)


def run(parameters: dict, player=None, session_memory=None) -> str:
    file_path = str(parameters.get("file_path", "")).strip()
    language = str(parameters.get("language") or "tur+eng").strip()
    output_path = str(parameters.get("output_path") or "").strip()

    if not file_path:
        return "Sir, hangi dosyayı OCR'lamamı istediğini belirtmedin."

    src = Path(file_path).expanduser()
    if not src.exists():
        return f"Sir, '{file_path}' bulunamadı."

    ready, msg = _tesseract_ready()
    if not ready:
        return f"Sir, {msg}"

    def log(m: str) -> None:
        if player:
            try:
                player.write_log(f"JARVIS: {m}")
            except Exception:
                pass

    try:
        from PIL import Image
        pages_text: list[str] = []

        if src.suffix.lower() in _IMAGE_EXTS:
            log(f"'{src.name}' OCR ile okunuyor…")
            with Image.open(src) as img:
                pages_text.append(_ocr_image(img, language))

        elif src.suffix.lower() == ".pdf":
            import pymupdf as fitz
            doc = fitz.open(src)
            log(f"'{src.name}' — {doc.page_count} sayfa OCR ile okunuyor…")
            zoom = _RENDER_DPI / 72
            matrix = fitz.Matrix(zoom, zoom)
            for i, page in enumerate(doc, start=1):
                pix = page.get_pixmap(matrix=matrix)
                img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
                pages_text.append(f"--- Sayfa {i} ---\n{_ocr_image(img, language)}")
            doc.close()

        else:
            return (f"Sir, '{src.suffix}' uzantısını desteklemiyorum — "
                     "sadece resim dosyaları (jpg/png/...) veya PDF.")

    except ImportError as e:
        return f"Sir, gerekli kütüphane eksik: {e}. install_library aracıyla kurulabilir."
    except Exception as e:
        return f"Sir, OCR sırasında hata oluştu: {e}"

    text = "\n\n".join(pages_text).strip()
    if not text:
        return f"Sir, '{src.name}' içinden okunabilir metin çıkaramadım."

    dest = Path(output_path).expanduser() if output_path else src.with_name(src.stem + "_ocr.txt")
    try:
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(text, encoding="utf-8")
    except Exception as e:
        return f"Sir, metni çıkardım ama '{dest}' konumuna kaydedemedim: {e}"

    log(f"OCR tamamlandı, metin '{dest}' konumuna kaydedildi.")
    preview = text[:400] + ("…" if len(text) > 400 else "")
    return f"'{src.name}' OCR ile okundu ve '{dest}' konumuna kaydedildi. İlk kısım: {preview}"
