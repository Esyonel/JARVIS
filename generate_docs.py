import os
import ast

def analyze_file(filepath):
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        tree = ast.parse(content)
        classes = [node.name for node in ast.walk(tree) if isinstance(node, ast.ClassDef)]
        functions = [node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)]
        docstring = ast.get_docstring(tree)
        return {"classes": classes, "functions": functions, "docstring": docstring}
    except Exception as e:
        return {"error": str(e)}

def main():
    base_dir = r"d:\nu\JARVIS"
    docs_dir = os.path.join(base_dir, "jarvis_docs")
    os.makedirs(docs_dir, exist_ok=True)
    
    skill_dirs = ["plugins", "actions"]
    all_skills = []
    
    for d in skill_dirs:
        path = os.path.join(base_dir, d)
        if not os.path.exists(path):
            continue
        
        for filename in os.listdir(path):
            if filename.endswith(".py") and filename != "__init__.py":
                skill_name = filename[:-3]
                filepath = os.path.join(path, filename)
                info = analyze_file(filepath)
                
                md_filename = f"{d}_{skill_name}.md"
                md_filepath = os.path.join(docs_dir, md_filename)
                
                with open(md_filepath, 'w', encoding='utf-8') as mf:
                    mf.write(f"# {skill_name} ({d})\n\n")
                    if info.get("error"):
                        mf.write(f"Error parsing file: {info['error']}\n")
                    else:
                        if info.get("docstring"):
                            mf.write(f"## Açıklama\n{info['docstring']}\n\n")
                        mf.write(f"## Sınıflar\n")
                        for cls in info.get("classes", []):
                            mf.write(f"- {cls}\n")
                        mf.write(f"\n## Fonksiyonlar\n")
                        for func in info.get("functions", []):
                            mf.write(f"- {func}\n")
                
                all_skills.append({"name": skill_name, "type": d, "file": md_filename})

    index_filepath = os.path.join(docs_dir, "index.md")
    with open(index_filepath, 'w', encoding='utf-8') as f:
        f.write("# JARVIS Yetenekleri (Skills) - Genel Bakış\n\n")
        f.write("Bu dosya, JARVIS asistanının sahip olduğu tüm eylem ve eklentilerin listesini içerir.\n\n")
        
        f.write("## Actions\n")
        for s in [x for x in all_skills if x["type"] == "actions"]:
            f.write(f"- [{s['name']}](./{s['file']})\n")
            
        f.write("\n## Plugins\n")
        for s in [x for x in all_skills if x["type"] == "plugins"]:
            f.write(f"- [{s['name']}](./{s['file']})\n")

if __name__ == '__main__':
    main()
