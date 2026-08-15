import sqlite3
import re
from typing import Dict, Any, List
from indexer import get_all_chunks

def generate_architecture_diagram(db_path: str = "codetrace.db") -> Dict[str, Any]:
    """
    Veritabanındaki kod parçalarından otomatik Mermaid.js Mimari Diyagramı üretir.
    """
    chunks = get_all_chunks(db_path)
    
    if not chunks:
        return {
            "status": "error",
            "message": "Diyagram üretilecek veritabanı kaydı bulunamadı.",
            "mermaid_code": ""
        }

    files = list(set([c["file_path"] for c in chunks]))
    
    mermaid_lines = ["graph TD"]
    mermaid_lines.append("    %% Codetrace AI - Auto-Generated Architecture Diagram")
    
    # Düğümleri (Nodes) ekleme
    file_ids = {}
    for idx, f in enumerate(files):
        node_id = f"Node_{idx}"
        file_ids[f] = node_id
        short_name = f.split("/")[-1]
        mermaid_lines.append(f'    {node_id}["📄 {short_name}"]')

    # Regex ile hassas bağımlılık eşleştirme
    added_edges = set()
    for c in chunks:
        source_file = c["file_path"]
        source_id = file_ids.get(source_file)
        
        for target_file in files:
            if source_file != target_file:
                target_name = target_file.split("/")[-1].replace(".py", "")
                target_id = file_ids.get(target_file)
                
                # Regex (\b): Kelime sınırlarında arama yapar (false-positive gürültüyü engeller)
                pattern = r'\b' + re.escape(target_name) + r'\b'
                if re.search(pattern, c["code_content"]) and (source_id, target_id) not in added_edges:
                    mermaid_lines.append(f"    {source_id} -->|uses| {target_id}")
                    added_edges.add((source_id, target_id))

    mermaid_code = "\n".join(mermaid_lines)
    
    return {
        "status": "success",
        "total_files": len(files),
        "total_relationships": len(added_edges),
        "mermaid_code": mermaid_code
    }

if __name__ == "__main__":
    result = generate_architecture_diagram()
    print("\n🎨 ÜRETİLEN MERMAID.JS MİMARİ ŞEMASI:\n")
    print(result["mermaid_code"])
