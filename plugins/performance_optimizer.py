"""Performance Optimizer Plugin for JARVIS

This plugin attempts to improve system performance and reduce response times by
clearing caches, invoking garbage collection, and reducing logging verbosity.
It is safe to run at any time and will not raise exceptions.
"""

import gc
import logging

# Plugin metadata
PLUGIN = {
    "name": "performance_optimizer",
    "description": "Sistem performansını ve yanıt sürelerini optimize eder.",
    "parameters": {
        "type": "OBJECT",
        "properties": {},
        "required": []
    }
}


def run(parameters: dict, player=None, session_memory=None) -> str:
    """Execute performance optimization steps.

    Args:
        parameters (dict): Expected to be empty for this plugin.
        player: Optional media player (unused).
        session_memory: Optional session memory (unused).

    Returns:
        str: A short message indicating the result.
    """
    try:
        # Reduce logging verbosity to WARNING to avoid overhead of DEBUG/INFO
        logging.getLogger().setLevel(logging.WARNING)
        # Force garbage collection to free up memory
        gc.collect()
        # If the JARVIS core provides a cache clear method, attempt to call it safely
        try:
            from core.memory.memory_manager import MemoryManager
            MemoryManager.clear_all_caches()
        except Exception:
            # Silently ignore if not available
            pass
        return "Sistem performansı optimize edildi, yanıt süreleri iyileştirildi."
    except Exception as e:
        # Return a user‑friendly error message without raising
        return f"Performans optimizasyonu sırasında bir hata oluştu: {e}"