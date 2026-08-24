import psutil

PLUGIN = {
    "name": "app_launch_verifier",
    "description": "Açtığınız uygulamanın doğru şekilde başlatılıp başlatılmadığını kontrol eder.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "app_name": {
                "type": "string",
                "description": "Kontrol edilecek uygulamanın ya da sürecin adı. Windows'ta .exe uzantısı olmadan, Linux/macOS'ta komut adı olarak verilebilir."
            }
        },
        "required": ["app_name"]
    }
}

def run(parameters: dict, player=None, session_memory=None) -> str:
    """Check if a given application/process is currently running.

    Args:
        parameters: Dict containing "app_name" key.
        player: Optional audio player (unused).
        session_memory: Optional session memory (unused).

    Returns:
        A short Turkish sentence indicating whether the application is running.
    """
    try:
        app_name = parameters.get("app_name", "").strip()
        if not app_name:
            return "Uygulama adı belirtilmedi."
        # Normalize name for comparison (case‑insensitive, ignore .exe extension on Windows)
        target = app_name.lower()
        if target.endswith('.exe'):
            target = target[:-4]
        # Iterate over all processes
        for proc in psutil.process_iter(['name']):
            try:
                proc_name = proc.info['name']
                if not proc_name:
                    continue
                proc_name_norm = proc_name.lower()
                if proc_name_norm.endswith('.exe'):
                    proc_name_norm = proc_name_norm[:-4]
                if proc_name_norm == target:
                    return f"{app_name} uygulaması başarılı bir şekilde çalışıyor."
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue
        return f"{app_name} uygulaması çalışmıyor ya da bulunamadı."
    except Exception as e:
        # Catch‑all to ensure the plugin never raises an exception to the caller
        return f"Uygulama kontrolü sırasında bir hata oluştu: {str(e)}"
