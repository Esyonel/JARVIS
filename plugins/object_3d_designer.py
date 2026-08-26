"""
Builds a real 3D mesh from a spoken description (or from an object JARVIS just
saw via screen_process/vision) by having the LLM write actual Python code
(trimesh primitives + boolean ops), running that code in a restricted
sandbox, then saving a PNG preview and exporting the mesh in whichever
format the target program needs (STL for 3D printing/TinkerCAD, OBJ for
Blender/SketchUp/Fusion 360 import, PLY, etc).

Not a photorealistic 3D scanner — from an image it builds a reasonable
primitive-based approximation of what the model describes seeing, same as a
person sketching an object from memory.

Before designing anything from scratch, it checks ready-made 3D model
repositories (Cults3D, Yeggi, MakerWorld, Thingiverse, Printables) for an
existing match — cheaper and usually higher-quality than generating
primitives when someone already made it. Tries the description as given
first; if every site comes back empty, retries once with an English
translation, since these repositories mostly index English text. It only
ever reports what it found (title/text + link); it never auto-downloads
anything, since that needs the user's own explicit go-ahead.
"""

import ast
import re
import uuid
from pathlib import Path

PLUGIN = {
    "name": "object_3d_designer",
    "description": (
        "Designs a real 3D model — from a spoken description, from an object "
        "the user just showed via screen/camera vision, or from shape/measurement "
        "details the user read out. First checks ready-made 3D model repositories "
        "(Cults3D, Yeggi, MakerWorld, Thingiverse, Printables — trying an English "
        "translation too if the original wording finds nothing) for an existing "
        "match and reports what it finds (title/text + link, nothing downloaded "
        "automatically); only if nothing suitable exists there — or force_generate "
        "is set — does it write "
        "actual Python code that builds the geometry itself, saves a preview image "
        "(PNG), and exports the model in the file format the user's target program "
        "needs (STL for 3D printers/TinkerCAD, OBJ for Blender/SketchUp/Fusion 360 "
        "import). Use this when the user asks to 'draw'/'design'/'model'/'find' a 3D "
        "object, not for 2D image generation."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "description": {
                "type": "STRING",
                "description": (
                    "What to build, as much detail as available: shape, approximate "
                    "dimensions, how parts relate. If the user showed an object via "
                    "vision, describe what you saw here."
                ),
            },
            "target_program": {
                "type": "STRING",
                "description": (
                    "Which program/use the file is for: 'printer', 'tinkercad', "
                    "'blender', 'fusion360', 'sketchup', or a raw extension like "
                    "'stl'/'obj'/'ply'. Defaults to 'stl' (printer-ready) if unclear."
                ),
            },
            "filename": {
                "type": "STRING",
                "description": "Optional short name for the saved files (no extension).",
            },
            "force_generate": {
                "type": "BOOLEAN",
                "description": (
                    "Set true to skip the Cults3D existing-model check and design from "
                    "scratch directly — e.g. the user already said no to the found "
                    "results, or explicitly asked for a custom/original design."
                ),
            },
        },
        "required": ["description"],
    },
}

OUT_DIR = Path(__file__).resolve().parent.parent / "generated_models"

# target_program names the user might say → real file extension. Proprietary
# project formats (.skp, .f3d) aren't writable by an open-source library —
# these programs all import OBJ/STL fine, so we save that instead and say so.
_FORMAT_MAP = {
    "printer": "stl", "yazici": "stl", "yazıcı": "stl", "3d yazici": "stl",
    "tinkercad": "stl",
    "blender": "obj",
    "fusion360": "obj", "fusion 360": "obj", "fusion": "obj",
    "sketchup": "obj",
    "stl": "stl", "obj": "obj", "ply": "ply",
}

def _search_cults3d(query: str, limit: int = 4) -> list[dict]:
    """Scrapes Cults3D's search results page — no official public search API
    exists, but the results are plain server-rendered HTML (unlike Yeggi,
    which blocks headless browsers, or Thingiverse/Printables/MyMiniFactory,
    which render results client-side via JS and can't be read from the raw
    HTML). Returns [] on any failure; the caller treats that as 'nothing
    found' and falls through to designing one instead."""
    try:
        import requests
        from bs4 import BeautifulSoup
    except Exception:
        return []

    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        resp = requests.get("https://cults3d.com/en/search", params={"q": query},
                             headers=headers, timeout=15)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        results = []
        for art in soup.select("article.crea")[:limit]:
            a = art.select_one("a.tbox-thumb")
            if not a or not a.get("href"):
                continue
            title_el = a.select_one(".drawer-title")
            title = (a.get("title") or (title_el.get_text(strip=True) if title_el else "")).strip()
            price_el = a.select_one(".crea-price")
            price = price_el.get_text(strip=True) if price_el else ""
            results.append({
                "title": title or query,
                "url": "https://cults3d.com" + a["href"],
                "price": price,
            })
        return results
    except Exception as e:
        print(f"[object_3d_designer] Cults3D search failed: {e}")
        return []


# name → search URL template ({q} = URL-encoded-ish query). Tried in order,
# through actions/browser_control.py's real persistent browser automation
# instead of fresh headless requests — Yeggi and Printables sit behind a
# Cloudflare Turnstile challenge that cannot and must not be auto-solved;
# MakerWorld and Thingiverse render results client-side via JS and can't be
# read from raw HTML at all. A real, persistent browser profile degrades
# gracefully: the first-ever visit to a Turnstile-protected site may surface
# the challenge page (the user solves it once in the window that pops up),
# every automated visit after that sails through on the saved cookie.
_BROWSER_SOURCES = [
    ("Yeggi",       "https://www.yeggi.com/q/{q}/"),
    ("MakerWorld",  "https://makerworld.com/en/search/models?keyword={q}"),
    ("Thingiverse", "https://www.thingiverse.com/search?q={q}"),
    ("Printables",  "https://www.printables.com/search/models?q={q}"),
]

_BLOCKED_MARKERS = (
    "checking whether you are human", "güvenlik doğrulaması yapılıyor",
    "browser error", "could not",
)


def _search_via_browser(name: str, url: str) -> str:
    """One repo site via the shared real-browser automation. Returns '' on
    any failure, timeout, or still-showing bot-check page."""
    try:
        from actions.browser_control import browser_control
        import time

        nav = browser_control({"action": "go_to", "url": url, "browser": "chrome"})
        if not str(nav).startswith("Opened"):
            return ""
        time.sleep(2.5)
        text = browser_control({"action": "get_text", "browser": "chrome"})
        if not text or any(m in text.lower() for m in _BLOCKED_MARKERS):
            return ""
        return text[:1200]
    except Exception as e:
        print(f"[object_3d_designer] {name} search failed: {e}")
        return ""


def _search_repo_sites(query: str) -> str:
    """Cults3D first (fast, no browser needed), then each slower
    browser-automation source in turn. Returns the first non-empty hit,
    labeled with its source; '' if every source came back empty."""
    found = _search_cults3d(query)
    if found:
        lines = [f"{i+1}. {r['title']} ({r['price'] or 'fiyat belirtilmemiş'}) — {r['url']}"
                  for i, r in enumerate(found)]
        return "Cults3D:\n" + "\n".join(lines)

    for name, url_tmpl in _BROWSER_SOURCES:
        text = _search_via_browser(name, url_tmpl.format(q=query.replace(" ", "+")))
        if text:
            return f"{name}:\n{text}"
    return ""


def _translate_to_english(text: str) -> str:
    """These repositories only index English text — a Turkish query mostly
    finds nothing even when a matching model exists. Reuses the same
    multi-provider pool as internet_research_self_improve.py."""
    try:
        from core.ai_text import generate
        out = generate(
            f"Translate this to English. Reply with ONLY the translated text, "
            f"nothing else, no quotes:\n{text}"
        ).strip().strip('"')
        return out
    except Exception as e:
        print(f"[object_3d_designer] translate failed: {e}")
        return ""


_ALLOWED_IMPORTS = {"trimesh", "numpy", "math"}
_BANNED_NAMES = {"os", "sys", "subprocess", "shutil", "socket", "requests",
                  "open", "exec", "eval", "compile", "__import__", "input",
                  "globals", "locals", "vars", "getattr", "setattr", "delattr"}

_SAFE_BUILTINS = {
    "len": len, "range": range, "float": float, "int": int, "str": str,
    "list": list, "tuple": tuple, "dict": dict, "min": min, "max": max,
    "abs": abs, "sum": sum, "enumerate": enumerate, "zip": zip,
    "round": round, "True": True, "False": False, "None": None,
    # Needed so the generated script's own `import trimesh, numpy as np` line
    # works — safe here because _validate_safe already restricted every
    # import in the code to _ALLOWED_IMPORTS before this ever runs.
    "__import__": __import__,
}


def _resolve_format(target_program: str) -> tuple[str, str]:
    """Returns (extension, note). note is non-empty when we substituted a
    proprietary format the target program actually can't be given directly."""
    key = (target_program or "").strip().lower()
    ext = _FORMAT_MAP.get(key, "stl")
    proprietary = {"sketchup": ".skp", "fusion360": ".f3d", "fusion 360": ".f3d", "fusion": ".f3d"}
    if key in proprietary:
        return ext, (f"{target_program.title()}'in kendi {proprietary[key]} formatını doğrudan "
                      f"yazamıyorum, ama .{ext} dosyasını İçe Aktar (Import) ile açabilirsin.")
    return ext, ""


def _validate_safe(code: str) -> None:
    """AST whitelist: only trimesh/numpy/math imports, no dangerous calls or
    dunder access. Raises ValueError on anything outside that."""
    tree = ast.parse(code)
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            names = [a.name.split(".")[0] for a in node.names] if isinstance(node, ast.Import) \
                else [node.module.split(".")[0] if node.module else ""]
            for n in names:
                if n not in _ALLOWED_IMPORTS:
                    raise ValueError(f"disallowed import: {n}")
        if isinstance(node, ast.Name) and node.id in _BANNED_NAMES:
            raise ValueError(f"disallowed name: {node.id}")
        if isinstance(node, ast.Attribute) and node.attr.startswith("__"):
            raise ValueError(f"disallowed dunder access: {node.attr}")
        # trimesh.creation.revolve's real signature is a positional-arg trap the
        # model keeps mis-calling — force it through revolve_safe() instead of
        # just hoping the prompt is followed.
        if (isinstance(node, ast.Attribute) and node.attr == "revolve"
                and isinstance(node.value, ast.Attribute) and node.value.attr == "creation"):
            raise ValueError(
                "do not call trimesh.creation.revolve directly — use the provided "
                "revolve_safe(linestring=points_2d, sections=64) helper instead"
            )


def _twisted_vase_safe(base_radius=3.0, top_radius=2.0, height=15.0,
                        lobes=6, lobe_depth=0.18, twist_turns=1.0,
                        height_steps=80, radial_steps=96):
    """Builds a fluted vase that visibly spirals as it rises. A plain circular
    revolve looks identical whether 'twisted' or not — a circle is
    rotationally symmetric — so a real spiral needs a lobed (non-circular)
    cross-section whose angular position rotates progressively with height.
    Returns a closed, watertight, solid trimesh.Trimesh (capped top/bottom).

    lobes: number of flutes/ridges around the rim.
    lobe_depth: 0-1, how pronounced the flutes are (0 = plain circle).
    twist_turns: how many full rotations the flutes complete top-to-bottom.
    """
    import numpy as np
    import trimesh

    heights = np.linspace(0, height, height_steps)
    thetas  = np.linspace(0, 2 * np.pi, radial_steps, endpoint=False)

    rings = []
    for h in heights:
        h_frac  = h / height
        r_base  = base_radius + (top_radius - base_radius) * h_frac
        twist   = twist_turns * 2 * np.pi * h_frac
        r       = r_base * (1 + lobe_depth * np.cos(lobes * (thetas - twist)))
        x, y    = r * np.cos(thetas), r * np.sin(thetas)
        z       = np.full_like(thetas, h)
        rings.append(np.stack([x, y, z], axis=1))
    rings = np.array(rings)  # (height_steps, radial_steps, 3)

    H, R, _ = rings.shape
    idx = lambda i, j: i * R + j
    side_faces = []
    for i in range(H - 1):
        for j in range(R):
            j2 = (j + 1) % R
            a, b, c, d = idx(i, j), idx(i, j2), idx(i + 1, j2), idx(i + 1, j)
            side_faces.append([a, b, c])
            side_faces.append([a, c, d])

    flat = rings.reshape(-1, 3)
    bottom_c, top_c = H * R, H * R + 1
    verts = np.vstack([flat, [[0, 0, 0.0]], [[0, 0, height]]])

    cap_faces = []
    for j in range(R):
        j2 = (j + 1) % R
        cap_faces.append([bottom_c, idx(0, j2), idx(0, j)])
        cap_faces.append([top_c, idx(H - 1, j), idx(H - 1, j2)])

    mesh = trimesh.Trimesh(vertices=verts, faces=np.array(side_faces + cap_faces), process=True)
    mesh.fix_normals()
    return mesh


def _extract_code(raw: str) -> str:
    m = re.search(r"```(?:python)?\s*(.*?)```", raw, re.DOTALL)
    return (m.group(1) if m else raw).strip()


def _generate_code(description: str, prior_error: str = "") -> str:
    from core.ai_text import generate

    retry_note = f"\n\nYour previous attempt failed with: {prior_error}\nFix it." if prior_error else ""
    prompt = (
        "Write a short Python script that builds a 3D mesh for this object using ONLY "
        "the 'trimesh' library (trimesh.creation.box/cylinder/icosphere/cone/annulus/"
        "torus(major_radius=..., minor_radius=...)/extrude_polygon etc.) and 'numpy' as np. "
        "For plain lathed shapes (cups, bowls, bottles — same cross-section all the way "
        "around) call the helper already provided in scope: "
        "revolve_safe(linestring=points_2d, sections=64) — do NOT call "
        "trimesh.creation.revolve directly, use revolve_safe instead; points_2d is an "
        "(n, 2) array of the profile's (radius, height) points.\n"
        "For a vase/object that visibly TWISTS, SPIRALS, or is FLUTED/RIBBED as it rises "
        "(a plain revolve looks identical whether twisted or not, since a circle has no "
        "angular features to twist) call the helper already provided in scope: "
        "twisted_vase_safe(base_radius=.., top_radius=.., height=.., lobes=.., "
        "lobe_depth=.., twist_turns=..) — pick lobes/lobe_depth/twist_turns to match how "
        "pronounced and how twisted the description asks for; it returns a ready, closed "
        "trimesh.Trimesh, use it directly as (part of) `mesh`.\n"
        "Combine primitives with trimesh.boolean.union([a, b]), "
        "trimesh.boolean.difference([a, b]), trimesh.boolean.intersection([a, b]) — these "
        "take a LIST of meshes and return one merged trimesh.Trimesh. Do NOT use +, -, & "
        "operators on Trimesh objects, they are not supported. For simple non-overlapping "
        "grouping (no real boolean needed) use trimesh.util.concatenate([a, b]). Position "
        "parts with .apply_translation()/.apply_transform() BEFORE combining them. The FINAL "
        "mesh (a single trimesh.Trimesh) must be assigned to a variable named exactly `mesh`.\n\n"
        f"Object to build: {description}\n\n"
        "Every distinct part mentioned in the object description (handle, spout, legs, "
        "lid, etc.) must be present as actual geometry in the final `mesh` — if a boolean "
        "op on one part keeps failing, fix or simplify THAT part, don't drop it.\n"
        "Rules: no imports other than trimesh and numpy, no file I/O, no comments, "
        "no markdown fences, no print statements, no other libraries, no input().\n"
        "Reply with ONLY the raw Python code." + retry_note
    )
    return _extract_code(generate(prompt))


def _revolve_safe(linestring, sections=64):
    """Wraps trimesh.creation.revolve with a minimal, collision-proof
    signature — the LLM keeps miscalling the real function's (linestring,
    angle, cap, sections, transform) signature with a stray positional arg
    that lands on `sections` and collides with an explicit sections= kwarg.
    Giving it only 2 keyword-only-in-practice params removes that whole
    class of TypeError."""
    import trimesh as _tm
    return _tm.creation.revolve(linestring=linestring, sections=sections)


def _render_preview(mesh, png_path: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from mpl_toolkits.mplot3d.art3d import Poly3DCollection

    fig = plt.figure(figsize=(5, 5))
    ax = fig.add_subplot(111, projection="3d")
    poly = Poly3DCollection(mesh.vertices[mesh.faces], alpha=0.85,
                             facecolor=(0.25, 0.55, 0.95), edgecolor=(0.1, 0.1, 0.1), linewidths=0.2)
    ax.add_collection3d(poly)
    bounds = mesh.bounds
    center = bounds.mean(axis=0)
    radius = max((bounds[1] - bounds[0]).max() / 2, 1e-6) * 1.15
    ax.set_xlim(center[0] - radius, center[0] + radius)
    ax.set_ylim(center[1] - radius, center[1] + radius)
    ax.set_zlim(center[2] - radius, center[2] + radius)
    ax.set_axis_off()
    ax.view_init(elev=22, azim=35)
    fig.tight_layout(pad=0)
    fig.savefig(png_path, dpi=150, transparent=False)
    plt.close(fig)


def run(parameters: dict, player=None, session_memory=None) -> str:
    description    = (parameters.get("description") or "").strip()
    target_program = (parameters.get("target_program") or "").strip()
    filename       = (parameters.get("filename") or "").strip()
    force_generate = bool(parameters.get("force_generate") or False)

    if not description:
        return "Ne çizmemi istediğini anlayamadım, biraz daha tarif eder misin?"

    if not force_generate:
        hit = _search_repo_sites(description)
        used_query = description
        if not hit:
            en = _translate_to_english(description)
            if en and en.strip().lower() != description.strip().lower():
                hit = _search_repo_sites(en)
                used_query = en
        if hit:
            note = f" (İngilizce aratıldı: '{used_query}')" if used_query != description else ""
            return (
                f"'{description}' için hazır modeller buldum{note}:\n\n{hit}\n\n"
                "Bunlardan birini istersen linkten indirebilirsin. Yine de kendim "
                "sıfırdan tasarlamamı istersen söyle."
            )

    ext, format_note = _resolve_format(target_program)

    if not filename:
        slug = re.sub(r"[^a-z0-9]+", "_", description.lower()).strip("_")[:40] or "model"
    else:
        slug = re.sub(r"[^a-zA-Z0-9_-]+", "_", filename)[:40]
    slug = f"{slug}_{uuid.uuid4().hex[:6]}"

    try:
        import trimesh
    except Exception:
        return "trimesh kütüphanesi kurulu değil, 3D model üretemiyorum."

    code = ""
    last_error = ""
    mesh = None
    for attempt in range(5):
        try:
            code = _generate_code(description, last_error)
            _validate_safe(code)
            ns: dict = {"trimesh": trimesh, "np": __import__("numpy"), "math": __import__("math"),
                        "revolve_safe": _revolve_safe, "twisted_vase_safe": _twisted_vase_safe,
                        "__builtins__": _SAFE_BUILTINS}
            exec(compile(code, "<object_3d_designer>", "exec"), ns)
            candidate = ns.get("mesh")
            if not isinstance(candidate, trimesh.Trimesh) or len(candidate.faces) == 0:
                raise ValueError("code did not produce a non-empty trimesh.Trimesh named 'mesh'")
            mesh = candidate
            break
        except Exception as e:
            last_error = str(e)[:300]
            print(f"[object_3d_designer] attempt {attempt + 1} failed: {last_error}")

    if mesh is None:
        return (f"'{description}' için 3D model üretemedim — kod her denemede hata verdi "
                f"({last_error}). Tarifi biraz basitleştirip tekrar dener misin?")

    try:
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        py_path  = OUT_DIR / f"{slug}.py"
        png_path = OUT_DIR / f"{slug}.png"
        model_path = OUT_DIR / f"{slug}.{ext}"

        py_path.write_text(code, encoding="utf-8")
        _render_preview(mesh, png_path)
        mesh.export(str(model_path))
    except Exception as e:
        return f"Model üretildi ama dosyalar kaydedilirken hata oldu: {e}"

    result = (
        f"'{description}' için modeli oluşturdum. Python kodu: {py_path.name}, "
        f"önizleme resmi: {png_path.name}, {ext.upper()} dosyası: {model_path.name}. "
        f"Hepsi generated_models klasöründe."
    )
    if format_note:
        result += f" Not: {format_note}"

    if player:
        try:
            player.write_log(f"JARVIS: {result}")
        except Exception:
            pass
    return result
