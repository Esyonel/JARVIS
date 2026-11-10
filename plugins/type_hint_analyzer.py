import os
import ast
import glob

PLUGIN = {
    "name": "type_hint_analyzer",
    "description": "Analyzes Python scripts in the workspace for missing type hints and potential type issues, offering improvement suggestions.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "target_dir": {
                "type": "string",
                "description": "Optional directory to scan (defaults to repository root)."
            }
        },
        "required": []
    }
}

class TypeHintVisitor(ast.NodeVisitor):
    def __init__(self, filename):
        self.filename = filename
        self.missing_hints = 0
        self.total_functions = 0

    def visit_FunctionDef(self, node):
        self.total_functions += 1
        has_return_hint = node.returns is not None
        has_arg_hints = all(
            arg.annotation is not None for arg in node.args.args if arg.arg != 'self'
        )
        if not (has_return_hint and has_arg_hints):
            self.missing_hints += 1
        self.generic_visit(node)

def run(parameters: dict, player=None, session_memory=None) -> str:
    try:
        target_dir = parameters.get("target_dir", ".")
        if not os.path.exists(target_dir):
            return "Specified directory does not exist."
        
        python_files = glob.glob(os.path.join(target_dir, "**/*.py"), recursive=True)
        # Filter out virtual environment folders
        python_files = [f for f in python_files if "pyenv" not in f and "venv" not in f]

        total_files = len(python_files)
        total_funcs = 0
        total_missing = 0

        for filepath in python_files:
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    tree = ast.parse(f.read(), filename=filepath)
                visitor = TypeHintVisitor(filepath)
                visitor.visit(tree)
                total_funcs += visitor.total_functions
                total_missing += visitor.missing_hints
            except Exception:
                continue

        if total_funcs == 0:
            return f"Analyzed {total_files} python files, no functions found to check."

        coverage = ((total_funcs - total_missing) / total_funcs) * 100
        return f"Type hint analysis complete. Scanned {total_files} files and {total_funcs} functions. Overall type hint coverage is approximately {coverage:.1f} percent. {total_missing} functions lack complete type hints."
    except Exception as e:
        return f"An error occurred during static analysis: {str(e)}"
