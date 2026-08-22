import requests
from typing import Dict, Any
from indexer import get_all_chunks, DB_PATH
from rag_engine import FOUNDRY_LOCAL_URL, DEFAULT_MODEL


def generate_repo_readme(model_name: str = DEFAULT_MODEL, db_path: str = DB_PATH) -> Dict[str, Any]:
    """
    Veritabanındaki GERÇEK indekslenmiş kod bileşenlerini kullanarak README üretir.
    Foundry Local erişilebilirse LLM çıktısını kullanır; erişilemezse indeksteki
    gerçek modüllerden otomatik Markdown README üretir.
    """
    chunks = get_all_chunks(db_path)

    if not chunks:
        return {
            "status": "error",
            "message": "Henüz indekslenmiş bir veritabanı kaydı bulunamadı. Lütfen önce yukarıdaki 'Restart' / 'Analyze' butonuna basarak repoyu indeksleyin.",
            "readme_markdown": ""
        }

    files_list = {c['file_path'] for c in chunks}

    sample_components = []
    for c in chunks[:15]:
        sample_components.append(f"• **{c['name']}** ({c['type']}) — `{c['file_path']}`")

    context_text = "\n".join(sample_components)

    system_prompt = (
        "You are Codetrace AI. Write a concise, professional GitHub README.md for this repository.\n"
        "Use ONLY these exact sections, nothing more:\n"
        "# Project Overview\n"
        "## Core Architecture & Modules\n"
        "## Key Capabilities\n"
        "STRICT RULES:\n"
        "- Do NOT add Installation, Usage Examples, or Conclusion sections.\n"
        "- Do NOT include any code, commands, or facts that are not explicitly present in the given components.\n"
        "- Do NOT rely on prior/general knowledge about this library — treat it as if you have never seen it before."
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

            unwanted_sections = ["## Installation", "## Usage Examples", "## Conclusion"]
            for sec in unwanted_sections:
                if sec in readme_text:
                    readme_text = readme_text.split(sec)[0]

            return {
                "status": "success",
                "readme_markdown": readme_text.strip()
            }
    except Exception as e:
        print(f"[README Generator] Foundry Local LLM Offline/Timeout, generating structured DB README: {e}")

    # Fallback: Robust Markdown generation directly from real DB chunks
    fallback_readme = [
        "# Codetrace Architecture Overview",
        "",
        "## Core Architecture & Modules",
        "### Analyzed Key Modules & Components:",
        context_text,
        "",
        "## Key Capabilities",
        f"- **Indexed Total Files:** {len(files_list)} source files analyzed",
        f"- **Indexed Total Chunks:** {len(chunks)} code components parsed via Python AST"
    ]

    return {
        "status": "success",
        "readme_markdown": "\n".join(fallback_readme)
    }


if __name__ == "__main__":
    result = generate_repo_readme()
    print(result.get("readme_markdown", result))
