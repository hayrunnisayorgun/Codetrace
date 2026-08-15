
import requests
import re
from typing import Dict, Any
from indexer import get_all_chunks
from rag_engine import FOUNDRY_LOCAL_URL, DEFAULT_MODEL

def generate_repo_readme(model_name: str = DEFAULT_MODEL, db_path: str = "codetrace.db") -> Dict[str, Any]:
    """
    Veritabanındaki kod mimarisini inceleyerek repo için otomatik README.md dökümanı üretir.
    """
    chunks = get_all_chunks(db_path)
    
    if not chunks:
        return {
            "status": "error",
            "message": "README üretilecek veritabanı kaydı bulunamadı.",
            "readme_markdown": ""
        }

    unique_components = set()
    for c in chunks[:10]:
        unique_components.add(f"File: {c['file_path']} | Component: {c['name']} ({c['type']})")
    
    context_text = "\n".join(list(unique_components))

    system_prompt = (
        "You are Codetrace AI. Write a concise, professional GitHub README.md for this repository.\n"
        "Use ONLY these exact sections:\n"
        "# Project Overview\n"
        "## Core Architecture & Modules\n"
        "## Key Capabilities\n"
        "Rule: Only state facts from the analyzed components."
    )

    user_prompt = f"Analyzed Repository Components:\n{context_text}"

    payload = {
        "model": model_name,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        "temperature": 0.1,
        "max_tokens": 500
    }

    try:
        response = requests.post(FOUNDRY_LOCAL_URL, json=payload, timeout=180)
        if response.status_code == 200:
            result = response.json()
            readme_text = result["choices"][0]["message"]["content"]
            
            # Post-Processing: İstenmeyen uydurma bölümleri kod seviyesinde kırpma
            unwanted_sections = ["## Installation", "## Usage Examples", "## Conclusion"]
            for sec in unwanted_sections:
                if sec in readme_text:
                    readme_text = readme_text.split(sec)[0]

            return {
                "status": "success",
                "readme_markdown": readme_text.strip()
            }
        else:
            return {"status": "error", "message": f"Status Code: {response.status_code} - {response.text}"}
    except Exception as e:
        return {"status": "error", "message": f"Bağlantı Hatası: {str(e)}"}

if __name__ == "__main__":
    result = generate_repo_readme()
    print("\n--- GENERATED README.MD ---\n")
    print(result.get("readme_markdown", result))
