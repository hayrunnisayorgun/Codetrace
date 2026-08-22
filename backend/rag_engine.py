import requests
from typing import Dict, Any
from search_engine import search_code_chunks

FOUNDRY_LOCAL_URL = "http://127.0.0.1:49454/v1/chat/completions"
DEFAULT_MODEL = "qwen2.5-coder-1.5b"

def ask_codetrace(query: str, model_name: str = DEFAULT_MODEL, confidence_threshold: float = 10.0) -> Dict[str, Any]:
    """
    RAG Akışı:
    1. İlgili kod parçalarını arar.
    2. Güven skorunu kontrol eder (Halüsinasyon engelleme).
    3. Mentörlük tonunda prompt hazırlar ve Foundry Local'a gönderir.
    """
    print(f"\n[INFO] '{query}' sorusu için kod tabanı taranıyor...")
    relevant_chunks = search_code_chunks(query, top_k=3)
    
    if not relevant_chunks or relevant_chunks[0]["score"] < confidence_threshold:
        return {
            "answer": "I couldn't find enough relevant code in the repository to answer your question with confidence.",
            "confidence_score": 0.0,
            "sources": []
        }
    
    top_score = relevant_chunks[0]["score"]
    
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

    payload = {
        "model": model_name,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        "temperature": 0.2,
        "max_tokens": 600
    }

    try:
        response = requests.post(FOUNDRY_LOCAL_URL, json=payload, timeout=180)
        if response.status_code == 200:
            result = response.json()
            answer = result["choices"][0]["message"]["content"]
        elif "is not loaded" in response.text:
            answer = (
                f"Foundry Local model '{model_name}' is not currently loaded. "
                f"Run `foundry model load {model_name}` and try again."
            )
        else:
            answer = f"Error from Foundry Local daemon (Status Code: {response.status_code})\nDetails: {response.text}"
    except requests.exceptions.Timeout:
        answer = "Foundry Local took too long to respond. The model may still be warming up — please try again."
    except requests.exceptions.ConnectionError:
        answer = "Could not connect to Foundry Local. Make sure the Foundry Local service is running on port 49454."
    except Exception as e:
        answer = f"Could not connect to Foundry Local daemon: {str(e)}"

    return {
        "answer": answer,
        "confidence_score": top_score,
        "sources": sources
    }

if __name__ == "__main__":
    test_query = "How does HTTP session handling work in requests?"
    response = ask_codetrace(test_query)
    
    print("\n" + "="*50)
    print(f"CONFIDENCE SCORE: %{response['confidence_score']}")
    print(f"SOURCES: {response['sources']}")
    print("="*50)
    print(f"ANSWER:\n\n{response['answer']}")
    print("="*50)
