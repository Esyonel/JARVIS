import os
import ast
from pathlib import Path

PLUGIN = {
    "name": "call_graph_visualizer",
    "description": "Statically analyzes all active Python scripts for function and class dependencies and generates a visual call graph showing the shortest execution path.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "target_function": {
                "type": "string",
                "description": "Optional target function or class name to compute the shortest execution path to."
            }
        },
        "required": []
    }
}

class CallGraphVisitor(ast.NodeVisitor):
    def __init__(self, filename):
        self.filename = filename
        self.current_function = None
        self.functions = set()
        self.calls = defaultdict(set) if 'defaultdict' in globals() else {}
        # simple dict fallback
        self.calls_dict = {}

    def visit_FunctionDef(self, node):
        old_func = self.current_function
        self.current_function = node.name
        self.functions.add(node.name)
        if old_func:
            if old_func not in self.calls_dict:
                self.calls_dict[old_func] = set()
            self.calls_dict[old_func].add(node.name)
        self.generic_visit(node)
        self.current_function = old_func

    def visit_ClassDef(self, node):
        old_func = self.current_function
        self.current_function = node.name
        self.functions.add(node.name)
        self.generic_visit(node)
        self.current_function = old_func

    def visit_Call(self, node):
        if self.current_function:
            if isinstance(node.func, ast.Name):
                called_name = node.func.id
                if self.current_function not in self.calls_dict:
                    self.calls_dict[self.current_function] = set()
                self.calls_dict[self.current_function].add(called_name)
            elif isinstance(node.func, ast.Attribute):
                called_name = node.func.attr
                if self.current_function not in self.calls_dict:
                    self.calls_dict[self.current_function] = set()
                self.calls_dict[self.current_function].add(called_name)
        self.generic_visit(node)

def run(parameters: dict, player=None, session_memory=None) -> str:
    try:
        target = parameters.get("target_function", "")
        root_dir = Path(".")
        py_files = list(root_dir.glob("**/*.py"))
        
        all_calls = {}
        all_nodes = set()
        
        for py_file in py_files:
            if "mcp_tools" in str(py_file) or "venv" in str(py_file):
                continue
            try:
                content = py_file.read_text(encoding="utf-8")
                tree = ast.parse(content, filename=str(py_file))
                visitor = CallGraphVisitor(str(py_file))
                visitor.visit(tree)
                all_nodes.update(visitor.functions)
                for k, v in visitor.calls_dict.items():
                    if k not in all_calls:
                        all_calls[k] = set()
                    all_calls[k].update(v)
            except Exception:
                continue

        graph_summary = f"Analyzed {len(py_files)} Python files. Found {len(all_nodes)} distinct functions/classes.\n"
        
        if target and target in all_nodes:
            # Find shortest path using BFS from any entry point or root
            # For simplicity, search paths from common entry points like 'run' or 'main'
            start_nodes = [n for n in all_nodes if n in ("run", "main", "setup")]
            if not start_nodes:
                start_nodes = list(all_nodes)[:1]
                
            shortest_path = None
            for start in start_nodes:
                queue = [[start]]
                visited = {start}
                found = False
                while queue:
                    path = queue.pop(0)
                    node = path[-1]
                    if node == target:
                        shortest_path = path
                        found = True
                        break
                    for neighbor in all_calls.get(node, []):
                        if neighbor not in visited:
                            visited.add(neighbor)
                            queue.append(path + [neighbor])
                if found:
                    break
            
            if shortest_path:
                graph_summary += f"Shortest execution path to '{target}': " + " -> ".join(shortest_path)
            else:
                graph_summary += f"No direct execution path found to target '{target}'."
        else:
            top_connections = sorted([(k, len(v)) for k, v in all_calls.items()], key=lambda x: x[1], reverse=True)[:5]
            graph_summary += "Top connected nodes: " + ", ".join([f"{k} ({c} calls)" for k, c in top_connections])

        return graph_summary
    except Exception as e:
        return f"Error generating call graph: {str(e)}"
