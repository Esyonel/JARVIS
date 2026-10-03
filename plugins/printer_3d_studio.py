"""
3D baskı stüdyosu — OpenSCAD ile şekil çizer, trimesh ile STL'yi kontrol eder,
Bambu Studio ile dilimler veya dosyayı Bambu Studio / Blender'da açar.

Çıktılar generated_models/ altına zaman damgalı isimlerle yazılır.
"""

import shutil
import subprocess
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
OUT_DIR = BASE_DIR / "generated_models"

OPENSCAD_CANDIDATES = [
    r"C:\Program Files\OpenSCAD (Nightly)\openscad.exe",
    r"C:\Program Files\OpenSCAD\openscad.exe",
]
BAMBU_CANDIDATES = [r"C:\Program Files\Bambu Studio\bambu-studio.exe"]
BLENDER_GLOB = r"C:\Program Files\Blender Foundation"

PLUGIN = {
    "name": "printer_3d_studio",
    "description": (
        "3D yazıcı için şekil çizer ve hazırlar. action='scad' ile verilen OpenSCAD "
        "kodundan STL ve PNG önizleme üretir (ölçüler mm). action='check' ile bir "
        "STL'nin su geçirmezliğini, hacmini ve boyutlarını kontrol eder. "
        "action='slice' ile STL'yi Bambu Studio ile dilimler. action='open' ile "
        "dosyayı Bambu Studio veya Blender'da açar."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "description": "scad | check | slice | open",
            },
            "scad_code": {
                "type": "STRING",
                "description": "action='scad' için tam OpenSCAD kodu (mm cinsinden).",
            },
            "name": {
                "type": "STRING",
                "description": "Çıktı dosyası için kısa isim (ör. 'kalemlik').",
            },
            "path": {
                "type": "STRING",
                "description": "check/slice/open için STL veya 3MF dosya yolu. Boşsa son üretilen STL kullanılır.",
            },
            "app": {
                "type": "STRING",
                "description": "action='open' için 'bambu' veya 'blender'. Varsayılan bambu.",
            },
        },
        "required": ["action"],
    },
}


def _find(candidates: list[str]) -> str | None:
    for c in candidates:
        if Path(c).exists():
            return c
    return None


def _find_blender() -> str | None:
    root = Path(BLENDER_GLOB)
    if not root.exists():
        return None
    found = sorted(root.glob("Blender */blender.exe"), reverse=True)
    return str(found[0]) if found else None


def _safe_name(name: str | None) -> str:
    name = (name or "model").strip() or "model"
    keep = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in name)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{keep[:40]}_{stamp}"


def _latest_stl() -> Path | None:
    stls = sorted(OUT_DIR.glob("*.stl"), key=lambda p: p.stat().st_mtime, reverse=True)
    return stls[0] if stls else None


def _resolve_path(raw: str | None) -> Path | None:
    if raw:
        p = Path(raw)
        if not p.is_absolute():
            p = OUT_DIR / p
        return p if p.exists() else None
    return _latest_stl()


def _check(stl: Path) -> str:
    import trimesh

    mesh = trimesh.load(str(stl), force="mesh")
    ext = mesh.extents
    lines = [
        f"Dosya: {stl.name}",
        f"Boyut (X×Y×Z): {ext[0]:.1f} × {ext[1]:.1f} × {ext[2]:.1f} mm",
        f"Üçgen sayısı: {len(mesh.faces)}",
        f"Su geçirmez: {'evet' if mesh.is_watertight else 'HAYIR — baskıda sorun çıkabilir'}",
    ]
    if mesh.is_watertight:
        lines.append(f"Hacim: {mesh.volume / 1000:.2f} cm³")
    if mesh.bounds[0][2] < -0.01:
        lines.append("Uyarı: model Z=0'ın altına iniyor, tablaya oturması için yükseltilmeli.")
    return "\n".join(lines)


def _scad(code: str, name: str | None) -> str:
    exe = _find(OPENSCAD_CANDIDATES)
    if not exe:
        return "OpenSCAD bulunamadı. Kurulu olduğundan emin ol."
    if not code or not code.strip():
        return "scad_code boş — çizilecek OpenSCAD kodu gerekli."

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    base = _safe_name(name)
    scad = OUT_DIR / f"{base}.scad"
    stl = OUT_DIR / f"{base}.stl"
    png = OUT_DIR / f"{base}.png"
    scad.write_text(code, encoding="utf-8")

    r = subprocess.run(
        [exe, "-o", str(stl), "--export-format", "binstl", str(scad)],
        capture_output=True, text=True, timeout=600,
    )
    if r.returncode != 0 or not stl.exists():
        err = (r.stderr or r.stdout).strip().splitlines()[-8:]
        return "OpenSCAD hata verdi:\n" + "\n".join(err)

    subprocess.run(
        [exe, "-o", str(png), "--imgsize=800,600", "--autocenter", "--viewall",
         "--colorscheme=Tomorrow Night", str(scad)],
        capture_output=True, text=True, timeout=300,
    )
    report = _check(stl)
    preview = f"\nÖnizleme: {png}" if png.exists() else ""
    return f"Model hazır: {stl}{preview}\n{report}"


def _slice(path: Path) -> str:
    exe = _find(BAMBU_CANDIDATES)
    if not exe:
        return "Bambu Studio bulunamadı."
    out = OUT_DIR / f"{path.stem}_sliced"
    out.mkdir(parents=True, exist_ok=True)
    r = subprocess.run(
        [exe, "--slice", "0", "--export-3mf", f"{path.stem}.gcode.3mf",
         "--outputdir", str(out), str(path)],
        capture_output=True, text=True, timeout=900,
    )
    made = list(out.glob("*.3mf")) + list(out.glob("*.gcode"))
    if made:
        return f"Dilimlendi: {made[0]}"
    err = (r.stderr or r.stdout).strip().splitlines()[-8:]
    return (
        "Bambu Studio komut satırından dilimleyemedi (yazıcı/filament profili gerekebilir). "
        "action='open' ile Bambu Studio'da açıp oradan dilimleyebilirsin.\n" + "\n".join(err)
    )


def _open(path: Path, app: str | None) -> str:
    if (app or "bambu").lower().startswith("blend"):
        exe = _find_blender()
        if not exe:
            return "Blender bulunamadı."
        script = (
            "import bpy;"
            "bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete();"
            f"bpy.ops.wm.stl_import(filepath=r'{path}')"
        )
        subprocess.Popen([exe, "--python-expr", script])
        return f"{path.name} Blender'da açılıyor."
    exe = _find(BAMBU_CANDIDATES)
    if not exe:
        return "Bambu Studio bulunamadı."
    subprocess.Popen([exe, str(path)])
    return f"{path.name} Bambu Studio'da açılıyor."


def run(parameters: dict, player=None, session_memory=None) -> str:
    action = (parameters.get("action") or "").strip().lower()
    try:
        if action == "scad":
            return _scad(parameters.get("scad_code", ""), parameters.get("name"))

        path = _resolve_path(parameters.get("path"))
        if path is None:
            return "Dosya bulunamadı. Önce action='scad' ile bir model üret veya geçerli bir yol ver."
        if action == "check":
            return _check(path)
        if action == "slice":
            return _slice(path)
        if action == "open":
            return _open(path, parameters.get("app"))
        return "Bilinmeyen action. scad, check, slice veya open kullan."
    except subprocess.TimeoutExpired:
        return "İşlem zaman aşımına uğradı."
    except Exception as e:
        return f"3D stüdyo hatası: {type(e).__name__}: {e}"
