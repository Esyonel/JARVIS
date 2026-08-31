"""
JARVIS plugin: control Blender through a minimal, deterministic automation layer.

Supported actions:
- open / launch
- locate
- help
- render
- create_cube
- export_obj

This plugin does not try to become a full Blender IDE. It focuses on the
practical JARVIS use-cases: open Blender, generate a quick scene, render a PNG,
export an OBJ. It can also be used by other JARVIS plugins or by voice-driven
commands in the desktop app.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

PLUGIN = {
    "name": "blender_controller",
    "description": (
        "Opens Blender, creates a basic scene, renders a PNG, exports an OBJ, "
        "or runs an integrated 3D workflow that generates a model and exports + renders it "
        "in one pass from JARVIS. Use this for: 'Blender'ı aç', 'küp oluştur', 'render al', "
        "'OBJ export et', '3D model üret'."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "description": "One of: open, launch, locate, help, render, create_cube, export_obj, generate, generate_3d, full_workflow.",
            },
            "blender_path": {
                "type": "STRING",
                "description": "Optional full path to blender.exe. If omitted, JARVIS will discover it automatically.",
            },
            "output_path": {
                "type": "STRING",
                "description": "Output file destination for render/export. Defaults to JARVIS/generated_models/blender_output.png or .obj.",
            },
            "object_name": {
                "type": "STRING",
                "description": "Name to use for the generated object, such as 'JarvisCube'.",
            },
            "description": {
                "type": "STRING",
                "description": "Text description for the generated 3D object. Example: 'mavi küp', 'silindir', 'küre'.",
            },
            "shape": {
                "type": "STRING",
                "description": "Optional object shape override: cube, cylinder, sphere, torus.",
            },
            "width": {
                "type": "INTEGER",
                "description": "Render width in pixels.",
            },
            "height": {
                "type": "INTEGER",
                "description": "Render height in pixels.",
            },
            "samples": {
                "type": "INTEGER",
                "description": "Cycles sample count for render quality.",
            },
            "run_as_admin": {
                "type": "BOOLEAN",
                "description": "Set true if Blender should be launched with elevated Windows permissions (UAC prompt may appear).",
            },
        },
        "required": ["action"],
    },
}


def _default_output_dir() -> Path:
    return Path(__file__).resolve().parent.parent / "generated_models"


def _candidate_blender_paths() -> list[str]:
    candidates = []
    for raw in (
        os.environ.get("BLENDER_PATH"),
        "C:/Program Files/Blender Foundation/Blender 5.2/blender.exe",
        "C:/Program Files/Blender Foundation/Blender 5.1/blender.exe",
        "C:/Program Files/Blender Foundation/Blender 4.5/blender.exe",
        "C:/Program Files/Blender Foundation/Blender 4.2/blender.exe",
        "C:/Program Files/Blender Foundation/Blender/blender.exe",
    ):
        if raw and raw.strip():
            candidates.append(raw.strip())
    # Also consider PATH resolution.
    try:
        found = subprocess.run(["where", "blender"], capture_output=True, text=True, shell=True, check=False)
        if found.returncode == 0:
            for line in found.stdout.splitlines():
                v = line.strip()
                if v:
                    candidates.append(v)
    except Exception:
        pass
    # unique ordered list
    ordered = []
    seen = set()
    for item in candidates:
        norm = item.replace("\\", "/")
        if norm not in seen:
            ordered.append(norm)
            seen.add(norm)
    return ordered


def _normalize_path(raw: str | None) -> str | None:
    if not raw:
        return None
    candidate = raw.strip().strip('"')
    if not candidate:
        return None
    candidate = candidate.replace("\\", "/")
    return candidate


def _locate_blender(blender_path: str | None = None) -> str | None:
    explicit = _normalize_path(blender_path)
    if explicit and Path(explicit).exists():
        return explicit

    for candidate in _candidate_blender_paths():
        p = Path(candidate)
        if p.exists():
            return str(p)
    return None


def _prepare_output_dir(output_path: str | None, default_name: str) -> str:
    base = Path(output_path).expanduser() if output_path else _default_output_dir() / default_name
    if output_path:
        path_obj = Path(output_path)
    else:
        path_obj = Path(base)
    path_obj.parent.mkdir(parents=True, exist_ok=True)
    return str(path_obj)


def _write_python_script(script_text: str, suffix: str = "jarvis_blender_task.py") -> str:
    out_dir = _default_output_dir()
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / suffix
    path.write_text(script_text, encoding="utf-8")
    return str(path)


def _launch_blender(blender_path: str, run_as_admin: bool = False):
    if run_as_admin:
        try:
            subprocess.run(
                [
                    "powershell",
                    "-NoProfile",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-Command",
                    f"Start-Process -FilePath '{blender_path}' -Verb RunAs",
                ],
                check=False,
                shell=False,
            )
            return True
        except Exception:
            pass
    subprocess.Popen([blender_path], shell=False)
    return True


def _build_render_script(output_path: str, width: int = 1920, height: int = 1080, samples: int = 64, object_name: str = "JarvisCube") -> str:
    safe_output = output_path.replace("\\", "/")
    script = f'''
import bpy
import os

bpy.ops.object.select_all(action="SELECT")
bpy.ops.object.delete(use_global=False)

scene = bpy.context.scene
scene.render.engine = "CYCLES"
scene.cycles.samples = {samples}
scene.render.resolution_x = {width}
scene.render.resolution_y = {height}

# Basic geometry
bpy.ops.mesh.primitive_cube_add(location=(0, 0, 0))
obj = bpy.context.active_object
obj.name = "{object_name}"

# Material
mat = bpy.data.materials.new(name="JarvisMat")
mat.use_nodes = True
bsdf = mat.node_tree.nodes["Principled BSDF"]
bsdf.inputs["Base Color"].default_value = (0.20, 0.65, 1.0, 1.0)
if obj.data.materials:
    obj.data.materials[0] = mat
else:
    obj.data.materials.append(mat)

# Light
bpy.ops.object.light_add(type="AREA", location=(3, 3, 5))
lamp = bpy.context.active_object
lamp.data.energy = 3000

# Camera
bpy.ops.object.camera_add(location=(5, -5, 4))
camera = bpy.context.active_object
camera.rotation_euler = (1.1, 0, 0.8)
scene.camera = camera

out = r"{safe_output}"
os.makedirs(os.path.dirname(out), exist_ok=True)
scene.render.filepath = out
bpy.ops.render.render(write_still=True)
print("JARVIS BLENDER RENDER: " + out)
'''
    return script


def _build_cube_script(output_path: str | None = None, object_name: str = "JarvisCube") -> str:
    target = output_path or str((_default_output_dir() / "jarvis_cube.obj").resolve())
    safe_output = target.replace("\\", "/")
    script = f'''
import bpy
import os

bpy.ops.object.select_all(action="SELECT")
bpy.ops.object.delete(use_global=False)

bpy.ops.mesh.primitive_cube_add(location=(0, 0, 0))
obj = bpy.context.active_object
obj.name = "{object_name}"

mat = bpy.data.materials.new(name="JarvisCubeMat")
mat.use_nodes = True
bsdf = mat.node_tree.nodes["Principled BSDF"]
bsdf.inputs["Base Color"].default_value = (0.25, 0.7, 0.95, 1.0)
if obj.data.materials:
    obj.data.materials[0] = mat
else:
    obj.data.materials.append(mat)

out = r"{safe_output}"
os.makedirs(os.path.dirname(out), exist_ok=True)

bpy.ops.wm.obj_export(filepath=out, export_selected_objects=True)
print("JARVIS BLENDER OBJ EXPORT: " + out)
'''
    return script


def _infer_shape(description: str | None, override: str | None) -> str:
    text = (override or description or "cube").lower()
    if "sphere" in text or "küre" in text or "top" in text:
        return "sphere"
    if "cylinder" in text or "silindir" in text or "boru" in text:
        return "cylinder"
    if "torus" in text or "halka" in text:
        return "torus"
    return "cube"


def _build_integrated_model_script(output_obj: str, output_png: str, description: str | None = None, object_name: str = "JarvisModel", shape: str | None = None, width: int = 1920, height: int = 1080, samples: int = 64) -> str:
    shape_name = _infer_shape(description, shape)
    obj_name = (object_name or "JarvisModel").replace('"', '')
    safe_obj = output_obj.replace("\\", "/")
    safe_png = output_png.replace("\\", "/")
    script = f'''
import bpy
import os

bpy.ops.object.select_all(action="SELECT")
bpy.ops.object.delete(use_global=False)

scene = bpy.context.scene
scene.render.engine = "CYCLES"
scene.cycles.samples = {samples}
scene.render.resolution_x = {width}
scene.render.resolution_y = {height}

shape = "{shape_name}"
obj = None
if shape == "sphere":
    bpy.ops.mesh.primitive_uv_sphere_add(radius=1.0, location=(0, 0, 0))
    obj = bpy.context.active_object
elif shape == "cylinder":
    bpy.ops.mesh.primitive_cylinder_add(radius=1.0, depth=2.0, location=(0, 0, 0))
    obj = bpy.context.active_object
elif shape == "torus":
    bpy.ops.mesh.primitive_torus_add(major_radius=1.2, minor_radius=0.35, location=(0, 0, 0))
    obj = bpy.context.active_object
else:
    bpy.ops.mesh.primitive_cube_add(size=2.0, location=(0, 0, 0))
    obj = bpy.context.active_object

obj.name = "{obj_name}"

mat = bpy.data.materials.new(name="JarvisMaterial")
mat.use_nodes = True
bsdf = mat.node_tree.nodes["Principled BSDF"]
bsdf.inputs["Base Color"].default_value = (0.20, 0.65, 1.0, 1.0)
if obj.data.materials:
    obj.data.materials[0] = mat
else:
    obj.data.materials.append(mat)

bpy.ops.object.light_add(type="AREA", location=(3, 3, 5))
lamp = bpy.context.active_object
lamp.data.energy = 2500

bpy.ops.object.camera_add(location=(5, -5, 4))
camera = bpy.context.active_object
camera.rotation_euler = (1.1, 0, 0.8)
scene.camera = camera

obj_path = r"{safe_obj}"
png_path = r"{safe_png}"
os.makedirs(os.path.dirname(obj_path), exist_ok=True)
os.makedirs(os.path.dirname(png_path), exist_ok=True)

bpy.ops.export_scene.obj(filepath=obj_path, use_selection=True)
scene.render.filepath = png_path
bpy.ops.render.render(write_still=True)

print("JARVIS BLENDER FULL FLOW: obj=" + obj_path + " png=" + png_path)
'''
    return script


def run(parameters: dict, player=None, session_memory=None) -> str:
    action = (parameters.get("action") or "help").strip().lower()
    blender_path = _locate_blender(parameters.get("blender_path"))
    run_as_admin = bool(parameters.get("run_as_admin", False))

    if action in {"help", "h"}:
        return (
            "Blender kontrol komutları: open/launch, locate, render, create_cube, export_obj, generate, generate_3d, full_workflow. "
            "Örnek: 'Blender'ı aç', 'render al', 'küp oluştur', 'OBJ export et', '3D model üret'."
        )

    if action in {"generate", "generate_model", "generate_3d", "full_workflow", "make_3d", "workflow"}:
        if not blender_path:
            return "3D model üretimi için Blender bulunamadı. blender_path verin."
        base_name = str(parameters.get("object_name") or "JarvisModel")
        desc = str(parameters.get("description") or "küp")
        shape = str(parameters.get("shape") or _infer_shape(desc, None))
        obj_path = _prepare_output_dir(parameters.get("output_path"), f"{base_name}_model.obj") if parameters.get("output_path") else _default_output_dir() / f"{base_name}_model.obj"
        png_path = _prepare_output_dir(None, f"{base_name}_render.png")
        if parameters.get("output_path"):
            stem = Path(str(parameters["output_path"]))
            obj_path = str(stem.with_suffix(".obj"))
            png_path = str(stem.with_suffix(".png"))
        else:
            obj_path = str(_default_output_dir() / f"{base_name}_model.obj")
            png_path = str(_default_output_dir() / f"{base_name}_render.png")
        width = int(parameters.get("width") or 1920)
        height = int(parameters.get("height") or 1080)
        samples = int(parameters.get("samples") or 64)
        script_text = _build_integrated_model_script(obj_path, png_path, description=desc, object_name=base_name, shape=shape, width=width, height=height, samples=samples)
        script_path = _write_python_script(script_text, "jarvis_generate_3d_workflow.py")
        try:
            if run_as_admin:
                subprocess.run(
                    [
                        "powershell",
                        "-NoProfile",
                        "-ExecutionPolicy",
                        "Bypass",
                        "-Command",
                        f"Start-Process -FilePath '{blender_path}' -ArgumentList '--background','--python','{script_path}' -Verb RunAs",
                    ],
                    check=False,
                    shell=False,
                )
            else:
                subprocess.Popen([blender_path, "--background", "--python", script_path], shell=False)
            return (
                f"Blender 3D akışı başlatıldı. Model: {obj_path} | Render: {png_path} | Şekil: {shape} | Admin={run_as_admin}"
            )
        except Exception as e:
            return f"Blender 3D akışı çalıştırılamadı: {e}"

    if action in {"locate", "find"}:
        if blender_path:
            return f"Blender bulundu: {blender_path}"
        return "Blender bulunamadı. Yolu manuel olarak blender_path ile verilebilir."

    if action in {"open", "launch", "start"}:
        if not blender_path:
            return "Blender yüklü görünmüyor. blender_path parametresiyle tam yol verin."
        try:
            _launch_blender(blender_path, run_as_admin=run_as_admin)
            return f"Blender başlatıldı: {blender_path} (admin={run_as_admin})"
        except Exception as e:
            return f"Blender başlatılamadı: {e}"

    if action in {"render", "render_scene"}:
        if not blender_path:
            return "Render için Blender bulunamadı. blender_path verin."
        output_path = _prepare_output_dir(parameters.get("output_path"), "jarvis_blender_render.png")
        width = int(parameters.get("width") or 1920)
        height = int(parameters.get("height") or 1080)
        samples = int(parameters.get("samples") or 64)
        object_name = str(parameters.get("object_name") or "JarvisCube")
        script_text = _build_render_script(output_path, width=width, height=height, samples=samples, object_name=object_name)
        script_path = _write_python_script(script_text, "jarvis_render_scene.py")
        try:
            subprocess.Popen([blender_path, "--background", "--python", script_path], shell=False)
            return f"Blender render başlatıldı. Çıktı: {output_path}. Script: {script_path}"
        except Exception as e:
            return f"Blender render çalıştırılamadı: {e}"

    if action in {"create_cube", "cube", "create_object"}:
        if not blender_path:
            return "Küp oluşturmak için Blender bulunamadı. blender_path verin."
        output_path = _prepare_output_dir(parameters.get("output_path"), "jarvis_cube.obj")
        object_name = str(parameters.get("object_name") or "JarvisCube")
        script_text = _build_cube_script(output_path=output_path, object_name=object_name)
        script_path = _write_python_script(script_text, "jarvis_create_cube.py")
        try:
            subprocess.Popen([blender_path, "--background", "--python", script_path], shell=False)
            return f"Blender küp oluşturma başlatıldı. OBJ: {output_path}."
        except Exception as e:
            return f"Blender küp oluşturma çalıştırılamadı: {e}"

    if action in {"export_obj", "obj_export"}:
        if not blender_path:
            return "OBJ export için Blender bulunamadı. blender_path verin."
        output_path = _prepare_output_dir(parameters.get("output_path"), "jarvis_export.obj")
        object_name = str(parameters.get("object_name") or "JarvisObject")
        script_text = _build_cube_script(output_path=output_path, object_name=object_name)
        script_path = _write_python_script(script_text, "jarvis_export_obj.py")
        try:
            subprocess.Popen([blender_path, "--background", "--python", script_path], shell=False)
            return f"Blender OBJ export başlatıldı. Çıktı: {output_path}."
        except Exception as e:
            return f"Blender OBJ export çalıştırılamadı: {e}"

    return (
        "Bilinmeyen Blender komutu. Kullanılabilir: open, locate, render, create_cube, export_obj, help."
    )
