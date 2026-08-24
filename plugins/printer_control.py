"""JARVIS plugin — printer status, queue, and control (win32print).

Distinct from device_manager.py: that one just lists which printers are
plugged in, this one checks whether the printer can actually print (paper,
toner, jam, offline) and can act on it (send a file, clear a stuck queue).
"""

import time
from pathlib import Path

import win32api
import win32print

PLUGIN = {
    "name": "printer_control",
    "description": (
        "Checks the printer's real status (ready, out of paper, paper jam, "
        "toner low, offline) and print queue, and can send a file to print or "
        "clear/cancel a stuck queue. Use for: 'yazıcım hazır mı', 'yazıcıda "
        "kağıt var mı', 'yazıcı çalışıyor mu', 'yazdırma kuyruğunda ne var', "
        "'şu dosyayı yazdır', 'yazdırmayı iptal et', 'kuyruğu temizle'. NOT "
        "for listing which printers are connected (use device_manager) and "
        "NOT for scanning documents (use scanner_control)."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "description": "'durum' (status — default), 'kuyruk' (queue), 'yazdir' (print a file), 'iptal' (cancel/clear queue).",
            },
            "file_path": {
                "type": "STRING",
                "description": "File to print. Only used when action is 'yazdir'.",
            },
            "printer_name": {
                "type": "STRING",
                "description": "Specific printer name. Omit to use the default printer.",
            },
        },
        "required": [],
    },
}

# PRINTER_STATUS_* bit flags (win32print doesn't expose all of these as
# constants across pywin32 versions, so they're hardcoded — these are the
# stable Win32 API values).
_STATUS_FLAGS = [
    (0x00000002, "hata var"),
    (0x00000008, "kağıt sıkışmış"),
    (0x00000010, "kağıdı bitmiş"),
    (0x00000040, "kağıt sorunu"),
    (0x00000080, "çevrimdışı"),
    (0x00040000, "toner/mürekkep bitmiş"),
    (0x00020000, "toner/mürekkep azalıyor"),
    (0x00400000, "kapağı açık"),
    (0x00000001, "duraklatılmış"),
    (0x00000200, "meşgul"),
    (0x00000400, "yazdırıyor"),
]

_JOB_STATUS_FLAGS = [
    (0x00000002, "yazdırılıyor"),
    (0x00000001, "duraklatıldı"),
    (0x00000004, "silindi"),
    (0x00000010, "hata"),
    (0x00000040, "kağıt sıkışmış"),
    (0x00000080, "kağıt bitmiş"),
]


def _resolve_printer_name(printer_name: str) -> str:
    return printer_name.strip() if printer_name and printer_name.strip() else win32print.GetDefaultPrinter()


def _status_text(status: int, flags: list) -> str:
    problems = [label for bit, label in flags if status & bit]
    return ", ".join(problems) if problems else "hazır"


def _check_status(printer_name: str) -> str:
    name = _resolve_printer_name(printer_name)
    handle = win32print.OpenPrinter(name)
    try:
        info = win32print.GetPrinter(handle, 2)
    finally:
        win32print.ClosePrinter(handle)

    status = info.get("Status", 0)
    jobs = info.get("cJobs", 0)
    state = _status_text(status, _STATUS_FLAGS)
    msg = f"'{name}' yazıcısı: {state}."
    if jobs:
        msg += f" Kuyrukta {jobs} iş var."
    return msg


def _check_queue(printer_name: str) -> str:
    name = _resolve_printer_name(printer_name)
    handle = win32print.OpenPrinter(name)
    try:
        jobs = win32print.EnumJobs(handle, 0, -1, 1)
    finally:
        win32print.ClosePrinter(handle)

    if not jobs:
        return f"'{name}' yazdırma kuyruğu boş."

    lines = []
    for job in jobs[:10]:
        doc = job.get("pDocument", "adsız belge")
        state = _status_text(job.get("Status", 0), _JOB_STATUS_FLAGS)
        lines.append(f"- {doc} ({state})")
    more = f" ve {len(jobs) - 10} iş daha" if len(jobs) > 10 else ""
    return f"'{name}' kuyruğunda {len(jobs)} iş var:\n" + "\n".join(lines) + more


def _cancel_queue(printer_name: str) -> str:
    name = _resolve_printer_name(printer_name)
    handle = win32print.OpenPrinter(name)
    try:
        jobs = win32print.EnumJobs(handle, 0, -1, 1)
        if not jobs:
            return f"'{name}' kuyruğu zaten boştu."
        for job in jobs:
            win32print.SetJob(handle, job["JobId"], 0, None, win32print.JOB_CONTROL_DELETE)
    finally:
        win32print.ClosePrinter(handle)
    return f"'{name}' yazdırma kuyruğundaki {len(jobs)} iş iptal edildi."


def _print_file(file_path: str, printer_name: str) -> str:
    path = Path((file_path or "").strip('"').strip())
    if not path.is_file():
        return f"Efendim, '{file_path}' dosyasını bulamadım."

    target = printer_name.strip() if printer_name and printer_name.strip() else None
    previous_default = None
    try:
        if target:
            previous_default = win32print.GetDefaultPrinter()
            if target != previous_default:
                win32print.SetDefaultPrinter(target)
        win32api.ShellExecute(0, "print", str(path), None, ".", 0)
        # give the OS a moment to hand the job off to that printer before
        # any default-printer restore below could race with it
        time.sleep(3)
        return f"'{path.name}' dosyası {target or _resolve_printer_name(None)} yazıcısına gönderildi."
    except Exception as e:
        return f"Efendim, yazdırma başlatılamadı: {e}"
    finally:
        if previous_default and previous_default != target:
            try:
                win32print.SetDefaultPrinter(previous_default)
            except Exception:
                pass


def run(parameters: dict, player=None, session_memory=None) -> str:
    action = (parameters.get("action") or "durum").strip().lower()
    printer_name = parameters.get("printer_name") or ""
    file_path = parameters.get("file_path") or ""

    try:
        if action.startswith("yazdir"):
            if not file_path:
                result = "Efendim, hangi dosyayı yazdıracağımı söylemediniz."
            else:
                result = _print_file(file_path, printer_name)
        elif action.startswith("kuyruk"):
            result = _check_queue(printer_name)
        elif action.startswith("iptal") or "temizle" in action:
            result = _cancel_queue(printer_name)
        else:
            result = _check_status(printer_name)
    except Exception as e:
        result = f"Efendim, yazıcıya ulaşamadım: {e}"

    _log(result, player)
    return result[:2500]


def _log(message: str, player=None) -> None:
    print(f"[PrinterControl] {message[:200]}")
    if player:
        try:
            player.write_log(f"JARVIS: {message}")
        except Exception:
            pass
