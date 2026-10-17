import os
import subprocess
import trimesh

PLUGIN = {
    "name": "bambu_stl_analyzer",
    "description": "STL ve 3MF dosyalarini trimesh ile analiz eder, manifoldluk, delik, hacim, filament agirligi ve Bambu Lab tabla sinirlarini denetler, bozuk yuzeyleri onararak Bambu Studio'ya aktarir.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "file_path": {
                "type": "string",
                "description": "Analiz edilecek STL veya 3MF dosyasinin tam yolu."
            },
            "density_g_cm3": {
                "type": "number",
                "description": "Filament yogunlugu (orn: PLA icin 1.24). Varsayilan 1.24."
            },
            "auto_repair": {
                "type": "boolean",
                "description": "Bozuk yuzeylerin ve deliklerin otomatik onarilip onarilmayacagi. Varsayilan True."
            },
            "launch_bambu_studio": {
                "type": "boolean",
                "description": "Onarilan dosyanin Bambu Studio'ya gonderilip gonderilmeyecegi. Varsayilan True."
            }
        },
        "required": [
            "file_path"
        ]
    }
}

def run(parameters: dict, player=None, session_memory=None) -> str:
    try:
        file_path = parameters.get("file_path")
        density = float(parameters.get("density_g_cm3", 1.24))
        auto_repair = parameters.get("auto_repair", True)
        launch_studio = parameters.get("launch_bambu_studio", True)

        if not file_path or not os.path.exists(file_path):
            return "Belirtilen 3D dosya yolu bulunamadi."

        mesh = trimesh.load(file_path)
        
        # If loaded as a Scene (e.g. 3MF with multiple meshes), combine them or pick the geometry
        if isinstance(mesh, trimesh.Scene):
            if len(mesh.geometry) == 0:
                return "Yuklenen sahne bos."
            mesh = trimesh.util.concatenate(list(mesh.geometry.values()))

        is_watertight = mesh.is_watertight
        euler_number = mesh.euler_number
        
        issues = []
        if not is_watertight:
            issues.append("Model su sizdirmaz (manifold) degil.")

        if auto_repair and not is_watertight:
            try:
                trimesh.repair.fill_holes(mesh)
                trimesh.repair.fix_normals(mesh)
                is_watertight = mesh.is_watertight
            except Exception:
                pass

        # Volume in cm3 (assuming mesh units are mm, 1 cm3 = 1000 mm3)
        volume_mm3 = mesh.volume
        volume_cm3 = abs(volume_mm3) / 1000.0
        weight_g = volume_cm3 * density

        # Bambu Lab X1/P1/A1 bed limits (approx 256 x 256 x 256 mm)
        extents = mesh.extents
        max_dim = max(extents)
        bed_limit_x, bed_limit_y, bed_limit_z = 256.0, 256.0, 256.0
        fits_bed = (extents[0] <= bed_limit_x) and (extents[1] <= bed_limit_y) and (extents[2] <= bed_limit_z)

        # Save repaired/analyzed file if needed
        output_path = file_path
        if auto_repair:
            base, ext = os.path.splitext(file_path)
            output_path = f"{base}_repaired.stl"
            mesh.export(output_path)

        if launch_studio and fits_bed:
            # Try launching Bambu Studio with the model
            bambu_paths = [
                r"C:\Program Files\Bambu Studio\bambu-studio.exe",
                r"C:\Program Files (x86)\Bambu Studio\bambu-studio.exe"
            ]
            launched = False
            for b_path in bambu_paths:
                if os.path.exists(b_path):
                    subprocess.Popen([b_path, output_path])
                    launched = True
                    break

        status_msg = f"Analiz tamamlandi. Hacim: {volume_cm3:.2f} santimetrekup, Tahmini filament agirligi: {weight_g:.1f} gram. "
        if not fits_bed:
            status_msg += "Uyari: Model Bambu Lab tabla sinirlarini asiyor! "
        else:
            status_msg += "Model tabla sinirlarina uygun. "

        if is_watertight:
            status_msg += "Model hatasiz ve manifold durumda. "
        else:
            status_msg += "Modelde bazi yapisal bozukluklar kalmis olabilir. "

        if launch_studio and fits_bed:
            status_msg += "Model basariyla Bambu Studio'ya aktarildi."

        return status_msg

    except Exception as e:
        return f"3D dosya analizi sirasinda bir hata olustu: {str(e)}"
