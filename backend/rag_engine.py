import requests
from typing import Dict, Any
from search_engine import search_code_chunks

# Foundry Local sunucusunun şu anki canlı adresi:
FOUNDRY_LOCAL_URL = "http://127.0.0.1:50824/v1/chat/completions"
DEFAULT_MODEL = "qwen2.5-coder-1.5b"


def ask_codetrace(query: str, model_name: str = DEFAULT_MODEL, confidence_threshold: float = 10.0) -> Dict[str, Any]:
    """
    RAG Akışı:
    1. İlgili kod parçalarını arar.
    2. Güven skorunu kontrol eder (Halüsinasyon engelleme).
    3. Mentörlük tonunda prompt hazırlar ve Foundry Local'a gönderir.
    """
    print(f"\n🔍 '{query}' sorusu için kod tabanı taranıyor...")
    relevant_chunks = search_code_chunks(query, top_k=3)
    
    if not relevant_chunks or relevant_chunks[0]["score"] < confidence_threshold:
        return {
            "answer": "⚠️ I couldn't find enough relevant code in the repository to answer your question with confidence.",
            "confidence_score": 0.0,
            "sources": []
        }
    
    top_score = relevant_chunks[0]["score"]
    
    # 2. Context (Kod bağlamı) metnini oluşturma
    context_text = ""
    sources = []
    for c in relevant_chunks:
        sources.append({
            "file": c["file_path"],
            "name": c["name"],
            "lines": f"{c['start_line']}-{c['end_line']}",
            "score": c["score"]
        })
        context_text += f"\n--- File: {c['file_path']} | Component: {c['name']} (Lines {c['start_line']}-{c['end_line']}) ---\n"
        context_text += f"{c['code_content']}\n"

    # 3. Junior Mentorship System Prompt (Öğretici & Mentor Tonu)
    system_prompt = (
        "You are Codetrace AI, an expert software architecture mentor. "
        "Your goal is to answer the user's question accurately based ONLY on the provided code snippets. "
        "Follow these rules:\n"
        "1. Explain WHY the code is structured this way if applicable.\n"
        "2. Highlight any design patterns used (e.g., Singleton, Factory, Dependency Injection).\n"
        "3. Keep your tone encouraging, professional, and educational for developers.\n"
        "4. If the code context does not contain the answer, strictly state that you cannot determine it from the given code."
    )

    user_prompt = f"Code Context:\n{context_text}\n\nUser Question: {query}"

    # 4. Foundry Local API Çağrısı
    payload = {
        "model": model_name,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        "temperature": 0.2
    }

    try:
        response = requests.post(FOUNDRY_LOCAL_URL, json=payload, timeout=60)
        if response.status_code == 200:
            result = response.json()
            answer = result["choices"][0]["message"]["content"]
        else:
            answer = f"❌ Error from Foundry Local daemon (Status Code: {response.status_code})\nDetails: {response.text}"
    except Exception as e:
        answer = f"❌ Could not connect to Foundry Local daemon: {str(e)}"

    return {
        "answer": answer,
        "confidence_score": top_score,
        "sources": sources
    }

if __name__ == "__main__":
    # Test Sorusu
    test_query = "How does the database connection work in this project?"

    response = ask_codetrace(test_query)
    
    print("\n" + "="*50)
    print(f"🛡️ CONFIDENCE SCORE: %{response['confidence_score']}")
    print(f"📌 SOURCES: {response['sources']}")
    print("="*50)
    print(f"🤖 CODETRACE AI MENTOR ANSWER:\n\n{response['answer']}")
    print("="*50)
