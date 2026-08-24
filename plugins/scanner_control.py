"""JARVIS plugin — document scanning via WIA (Windows Image Acquisition).

Uses the same multifunction device as printer_control.py (Canon MF460) but
as a scanner: connects to the first WIA scanner found, scans from the top
feeder if loaded (else the flatbed), and saves the result as a PDF — every
page from the feeder combined into one PDF, unless single_page is set.
"""

import re
import tempfile
import time
from pathlib import Path

import win32com.client
from PIL import Image

PLUGIN = {
    "name": "scanner_control",
    "description": (
        "Scans a document or photo using the connected scanner and saves it "
        "as a PDF file. Use for: 'tara', 'scan yap', 'şunu tara', 'belgeyi "
        "tarar mısın', 'yazıcıdan tarama yap'. When the user just says 'tara' "
        "or 'scan yap' without saying 'fotoğraf', ALWAYS scan in 'belge' mode "
        "— never guess 'fotograf'. If the feeder has several pages loaded, "
        "all of them are scanned into ONE combined PDF, unless the user says "
        "'tek sayfa tarama' (single-page scan), which stops after one page. "
        "NOT for printing (use printer_control) or listing connected devices "
        "(use device_manager)."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "mode": {
                "type": "STRING",
                "description": "'belge' (document — 300 DPI, smaller file; this is the default and what a plain 'tara'/'scan yap' means) or 'fotograf' (photo — 600 DPI, higher quality; only when the user explicitly says photo/fotoğraf). Same split as the Canon scan utility's 'Belge'/'Fotoğraf' buttons. Omit this parameter entirely unless the user specified which one.",
            },
            "single_page": {
                "type": "BOOLEAN",
                "description": "true only when the user explicitly says 'tek sayfa tarama' — stops after one page even if the feeder has more. Omit/false for a normal 'tara'/'scan yap', which scans every page in the feeder into one combined PDF.",
            },
            "file_name": {
                "type": "STRING",
                "description": "Optional name for the saved scan (without extension). Defaults to a timestamp.",
            },
        },
        "required": [],
    },
}

_OUT_DIR = Path("D:/02-XIRAMTAU/30-Scan")
_WIA_FORMAT_JPEG = "{B96B3CAE-0728-11D3-9D7B-0000F81EF32E}"
_WIA_DEVICE_TYPE_SCANNER = 1

# WIA_DATA_TYPE: 0=threshold(1-bit B&W), 2=grayscale, 3=color(24-bit).
# NOTE: item.Properties(...) must be indexed by NAME, not by the numeric
# WIA property ID — passing the ID is silently interpreted as an ordinal
# collection index and raises "index out of range".
_DATA_TYPE_GRAYSCALE = 2
_DATA_TYPE_COLOR = 3

_MODES = {
    # Matches the user's own Canon scan-utility settings: Belge Tarama =
    # Renk (color) / A4 / 300 dpi.
    "belge":    {"dpi": 300, "data_type": _DATA_TYPE_COLOR},
    "fotograf": {"dpi": 600, "data_type": _DATA_TYPE_COLOR},
}

_A4_WIDTH_MM = 210
_A4_HEIGHT_MM = 297
_MM_PER_INCH = 25.4


def _mm_to_px(mm: float, dpi: int) -> int:
    return round(mm / _MM_PER_INCH * dpi)


def _set_property(item, name: str, value) -> None:
    """Best-effort — not every WIA driver supports every property."""
    try:
        item.Properties(name).Value = value
    except Exception:
        pass


_IMG_NAME_RE = re.compile(r"^IMG_(\d{8})_(\d{4})$")


def _next_img_name() -> str:
    """Matches the Canon scan utility's own naming: IMG_YYYYMMDD_NNNN,
    numbered sequentially across whatever's already in the folder (not
    reset per day) so it keeps counting up after Canon's own scans too."""
    today = time.strftime("%Y%m%d")
    last_seq = 0
    for existing in _OUT_DIR.glob("IMG_*_*.*"):
        m = _IMG_NAME_RE.match(existing.stem)
        if m:
            last_seq = max(last_seq, int(m.group(2)))
    return f"IMG_{today}_{last_seq + 1:04d}"


def _find_scanner():
    manager = win32com.client.Dispatch("WIA.DeviceManager")
    for info in manager.DeviceInfos:
        if info.Type == _WIA_DEVICE_TYPE_SCANNER:
            return info
    return None


# Standard WIA document-handling bit flags (device-level properties, not
# item-level): whoever has paper loaded in the top feeder (ADF) wins —
# only fall back to the flatbed glass when the feeder is empty.
_DOC_HANDLING_STATUS = "Document Handling Status"
_DOC_HANDLING_SELECT = "Document Handling Select"
_FEED_READY = 0x0001
_FEEDER = 0x0001
_FLATBED = 0x0002


def _feeder_has_paper(device) -> bool:
    try:
        return bool(device.Properties(_DOC_HANDLING_STATUS).Value & _FEED_READY)
    except Exception:
        return False


def _select_source(device) -> bool:
    """Returns True if the feeder (ADF) was selected, False for flatbed."""
    from_feeder = _feeder_has_paper(device)
    try:
        device.Properties(_DOC_HANDLING_SELECT).Value = _FEEDER if from_feeder else _FLATBED
    except Exception:
        pass
    return from_feeder


def _transfer_page(item) -> Image.Image:
    """Transfers one page and returns it as a real, decoded PIL Image —
    re-encoded through a temp file since some drivers ignore the requested
    FormatID and hand back their native format (e.g. BMP) regardless."""
    image = item.Transfer(_WIA_FORMAT_JPEG)
    # WIA's SaveFile() refuses to write to a path that already exists, so the
    # temp path must be generated, never pre-created.
    tmp_path = Path(tempfile.gettempdir()) / f"jarvis_wia_scan_{time.time_ns()}.tmp"
    try:
        # The driver can hold the transferred buffer/file briefly after
        # Transfer() returns, causing a transient sharing violation on the
        # very next call — retry both SaveFile and the read that follows it.
        for attempt in range(6):
            try:
                image.SaveFile(str(tmp_path))
                break
            except OSError:
                if attempt == 5:
                    raise
                time.sleep(0.5)
        for attempt in range(6):
            try:
                with Image.open(tmp_path) as img:
                    return img.convert("RGB").copy()
            except (PermissionError, OSError):
                if attempt == 5:
                    raise
                time.sleep(0.3)
    finally:
        # Best-effort — a still-locked temp file (e.g. antivirus scanning it)
        # must never turn an already-successful scan into a reported failure.
        try:
            tmp_path.unlink(missing_ok=True)
        except OSError:
            pass


def _scan(mode: str, file_name: str, single_page: bool) -> str:
    settings = _MODES.get(mode, _MODES["belge"])

    info = _find_scanner()
    if info is None:
        return "Efendim, bağlı bir tarayıcı bulamadım."

    device = info.Connect()
    if device.Items.Count == 0:
        return "Efendim, tarayıcıdan görüntü kaynağı alınamadı."

    from_feeder = _select_source(device)

    item = device.Items[1]
    dpi = settings["dpi"]

    def _configure_item():
        _set_property(item, "Horizontal Resolution", dpi)
        _set_property(item, "Vertical Resolution", dpi)
        _set_property(item, "Data Type", settings["data_type"])
        # Extent is in PIXELS, not inches — it does NOT auto-scale when the
        # resolution changes, so without this the scan area shrinks to
        # whatever a previous lower-DPI default left behind (cropped to a
        # corner of the page instead of the full A4 sheet).
        _set_property(item, "Horizontal Start Position", 0)
        _set_property(item, "Vertical Start Position", 0)
        _set_property(item, "Horizontal Extent", _mm_to_px(_A4_WIDTH_MM, dpi))
        _set_property(item, "Vertical Extent", _mm_to_px(_A4_HEIGHT_MM, dpi))

    _configure_item()
    pages = [_transfer_page(item)]

    # The flatbed only ever has one page. The feeder can have several —
    # unless the user asked for a single page, keep pulling sheets until
    # it's empty and combine them into one PDF (matches Canon's plain
    # "PDF" data format; single_page matches its "split into files" one).
    if from_feeder and not single_page:
        while _feeder_has_paper(device):
            _configure_item()
            try:
                pages.append(_transfer_page(item))
            except Exception:
                break

    _OUT_DIR.mkdir(parents=True, exist_ok=True)
    name = (file_name or "").strip() or _next_img_name()
    if not name.lower().endswith(".pdf"):
        name += ".pdf"
    out_path = _OUT_DIR / name
    if out_path.exists():
        out_path.unlink()

    first, rest = pages[0], pages[1:]
    if rest:
        first.save(out_path, "PDF", resolution=float(dpi), save_all=True, append_images=rest)
    else:
        first.save(out_path, "PDF", resolution=float(dpi))

    return "Tarama yapıldı."


def run(parameters: dict, player=None, session_memory=None) -> str:
    mode = (parameters.get("mode") or "belge").strip().lower()
    file_name = parameters.get("file_name") or ""
    single_page = bool(parameters.get("single_page"))
    try:
        result = _scan(mode, file_name, single_page)
    except Exception as e:
        result = f"Efendim, tarama başarısız oldu: {e}"

    _log(result, player)
    return result[:2000]


def _log(message: str, player=None) -> None:
    print(f"[ScannerControl] {message[:200]}")
    if player:
        try:
            player.write_log(f"JARVIS: {message}")
        except Exception:
            pass
