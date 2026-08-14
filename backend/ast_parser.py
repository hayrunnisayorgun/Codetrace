import ast
from typing import List, Dict, Any


def _extract_methods(class_node: ast.ClassDef, lines: List[str], file_path: str) -> List[Dict[str, Any]]:
    """Bir sınıfın içindeki metodları ayrı, nitelikli isimlerle (ClassName.method_name) chunk'lar."""
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
    Python kodunu AST ile tarar. Sadece üst seviye (top-level) fonksiyon ve
    sınıfları ayırır; sınıf metodlarını da ayrıca "ClassName.method_name"
    formatında ayrı chunk'lar olarak ekler (tekrarsız, nitelikli isimlerle).
    """
    chunks = []

    try:
        tree = ast.parse(code_content)
    except SyntaxError:
        print(f"⚠️ {file_path} dosyasında SyntaxError oluştu, ham metin olarak alınıyor.")
        return [{
            "file_path": file_path,
            "name": "raw_file",
            "type": "file",
            "start_line": 1,
            "end_line": len(code_content.splitlines()),
            "code_content": code_content
        }]

    lines = code_content.splitlines()

    # Sadece dosyanın en dış seviyesini geziyoruz (ast.walk değil!)
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

            # Sınıfsa, metodlarını da ayrıca aranabilir chunk yapıyoruz
            if isinstance(node, ast.ClassDef):
                chunks.extend(_extract_methods(node, lines, file_path))

    return chunks


if __name__ == "__main__":
    sample_code = """
def calculate_sum(a, b):
    # İki sayıyı toplar
    return a + b

class User:
    def __init__(self, name):
        self.name = name

    def get_name(self):
        return self.name
"""
    result = parse_python_code(sample_code, "sample.py")
    print(f"✅ {len(result)} adet kod parçası (chunk) ayrıştırıldı:\n")
    for item in result:
        print(f"📌 [{item['type'].upper()}] {item['name']} (Satır {item['start_line']}-{item['end_line']}):")
        print(f"{item['code_content']}\n" + "-" * 40)