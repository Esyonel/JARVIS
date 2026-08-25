import importlib.util
import re
import subprocess
import sys

PLUGIN = {
    "name": "install_library",
    "description": (
        "Installs a Python library from PyPI into Jarvis's active Python environment. "
        "Use when a required library is missing."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "package": {
                "type": "STRING",
                "description": "PyPI package name, for example requests or opencv-python.",
            },
            "import_name": {
                "type": "STRING",
                "description": "Optional Python import name when it differs from the package name, for example cv2.",
            },
            "version": {
                "type": "STRING",
                "description": "Optional exact or compatible version, for example 2.31.0 or >=1.2.",
            },
        },
        "required": ["package"],
    },
}

_PACKAGE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
_IMPORT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_.]*$")
_VERSION_RE = re.compile(r"^(?:==|>=|<=|~=|!=|>|<)?[A-Za-z0-9][A-Za-z0-9.*+!-]{0,31}$")


def _pip_show(package: str) -> bool:
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pip", "show", package],
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return result.returncode == 0


def _import_available(import_name: str) -> bool:
    try:
        return importlib.util.find_spec(import_name) is not None
    except (ImportError, ModuleNotFoundError, ValueError):
        return False


def run(parameters: dict, player=None, session_memory=None) -> str:
    package = str(parameters.get("package", "")).strip()
    import_name = str(parameters.get("import_name", "")).strip()
    version = str(parameters.get("version", "")).strip()

    if not _PACKAGE_RE.fullmatch(package):
        return "Geçersiz paket adı. Yalnızca PyPI paket adları kullanılabilir."
    if import_name and not _IMPORT_RE.fullmatch(import_name):
        return "Geçersiz Python import adı."
    if version and not _VERSION_RE.fullmatch(version):
        return "Geçersiz paket sürümü."

    if _pip_show(package):
        if not version and (not import_name or _import_available(import_name)):
            return f"{package} zaten kurulu."

    requirement = package + (version if version.startswith(("==", ">=", "<=", "~=", "!=", ">", "<")) else f"=={version}" if version else "")
    try:
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "pip",
                "install",
                requirement,
                "--disable-pip-version-check",
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=600,
        )
    except subprocess.TimeoutExpired:
        return f"{package} kurulumu zaman aşımına uğradı."
    except OSError as error:
        return f"pip çalıştırılamadı: {error}"

    if result.returncode != 0:
        details = (result.stderr or result.stdout).strip().splitlines()
        return f"{package} kurulamadı: {details[-1][:240] if details else 'pip hata döndürdü.'}"

    if import_name and not _import_available(import_name):
        return f"{package} kuruldu ancak '{import_name}' importu doğrulanamadı."
    return f"{package} başarıyla kuruldu."