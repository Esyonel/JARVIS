PLUGIN = {
    "name": "blender_professional_tutor",
    "description": "Provides concise guidance on using Blender at a professional level.",
    "parameters": {
        "type": "OBJECT",
        "properties": {},
        "required": []
    }
}

def run(parameters: dict, player=None, session_memory=None) -> str:
    """Return a short spoken response about professional Blender usage.

    Parameters are accepted for future extensibility but currently ignored.
    Any unexpected error is caught and an error message is returned.
    """
    try:
        # In a full implementation, we could inspect 'parameters' for a specific
        # query (e.g., "modeling", "animation", "rendering"), but for now we
        # provide a generic helpful response.
        return (
            "Blender konusunda profesyonel düzeyde rehberlik sağlayabilirim. "
            "Modelleme, animasyon, ışıklandırma ya da render ayarları hakkında "
            "sormak istediğiniz bir şey var mı?"
        )
    except Exception as e:
        # Ensure the plugin never raises an exception to the caller.
        return f"Blender rehberi çalıştırılırken bir hata oluştu: {e}"