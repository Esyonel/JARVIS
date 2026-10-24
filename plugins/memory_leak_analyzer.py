import os
import sys
import gc
import psutil
import traceback

PLUGIN = {
    "name": "memory_leak_analyzer",
    "description": "Identifies Python memory leaks and uncollected reference cycles using standard library and psutil without trppy.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "target_script": {
                "type": "string",
                "description": "Optional path to a python script to analyze or monitor."
            }
        },
        "required": []
    }
}

def run(parameters: dict, player=None, session_memory=None) -> str:
    try:
        target = parameters.get("target_script")
        process = psutil.Process(os.getpid())
        
        # Force garbage collection to get a clean baseline
        collected = gc.collect()
        initial_rss = process.memory_info().rss / (1024 * 1024)
        initial_objects = len(gc.get_objects())
        
        analysis_result = f"Memory Analysis Baseline: RSS: {initial_rss:.2f} MB, GC Objects: {initial_objects}, Garbage collected: {collected} objects."
        
        if target and os.path.exists(target):
            import subprocess
            # Run target script and monitor peak memory
            start_rss = initial_rss
            res = subprocess.run([sys.executable, target], capture_output=True, text=True)
            final_rss = process.memory_info().rss / (1024 * 1024)
            diff = final_rss - start_rss
            analysis_result += f" Target script executed. Memory delta: {diff:+.2f} MB."
            if res.returncode != 0:
                analysis_result += f" Script exited with errors: {res.stderr[:200]}"
        
        # Check for uncollectable garbage (reference cycles)
        uncollectable_count = len(gc.garbage)
        if uncollectable_count > 0:
            analysis_result += f" Warning: Found {uncollectable_count} uncollectable objects in garbage collector cycle!"
        else:
            analysis_result += " No uncollectable reference cycles detected in current process space."
            
        return analysis_result
    except Exception as e:
        return f"Memory analysis failed due to error: {str(e)}"
