import ast
from typing import List, Dict, Any


def _extract_methods(class_node: ast.ClassDef, lines: List[str], file_path: str) -> List[Dict[str, Any]]:
    """Chunk a class's methods separately, qualified as ClassName.method_name."""
    method_chunks = []
    for node in class_node.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            start_line = node.lineno
            end_line = getattr(node, 'end_lineno', start_line)
            snippet = "\n".join(lines[start_line - 1: end_line])

            method_chunks.append({
                "file_path": file_path,
                "name": f"{class_node.name}.{node.name}",
                "type": "method",
                "start_line": start_line,
                "end_line": end_line,
                "code_content": snippet
            })
    return method_chunks


def parse_python_code(code_content: str, file_path: str) -> List[Dict[str, Any]]:
    """
    Parse Python source with `ast`. Only top-level functions and classes are
    split out, plus each class method as its own chunk named
    "ClassName.method_name" -- qualified, so names stay unambiguous.
    """
    chunks = []

    try:
        tree = ast.parse(code_content)
    except SyntaxError:
        print(f"[WARNING] SyntaxError in {file_path}; storing it as raw text.")
        return [{
            "file_path": file_path,
            "name": "raw_file",
            "type": "file",
            "start_line": 1,
            "end_line": len(code_content.splitlines()),
            "code_content": code_content
        }]

    lines = code_content.splitlines()

    # Walk only the module top level -- deliberately not ast.walk().
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            chunk_type = "class" if isinstance(node, ast.ClassDef) else "function"
            start_line = node.lineno
            end_line = getattr(node, 'end_lineno', start_line)
            snippet = "\n".join(lines[start_line - 1: end_line])

            chunks.append({
                "file_path": file_path,
                "name": node.name,
                "type": chunk_type,
                "start_line": start_line,
                "end_line": end_line,
                "code_content": snippet
            })

            # For a class, index its methods as separately searchable chunks.
            if isinstance(node, ast.ClassDef):
                chunks.extend(_extract_methods(node, lines, file_path))

    return chunks


if __name__ == "__main__":
    sample_code = """
def calculate_sum(a, b):
    # Adds two numbers
    return a + b

class User:
    def __init__(self, name):
        self.name = name

    def get_name(self):
        return self.name
"""
    result = parse_python_code(sample_code, "sample.py")
    print(f"[SUCCESS] Parsed {len(result)} chunks:\n")
    for item in result:
        print(f"[{item['type'].upper()}] {item['name']} (lines {item['start_line']}-{item['end_line']}):")
        print(f"{item['code_content']}\n" + "-" * 40)