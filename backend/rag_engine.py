import json
import requests
from typing import Dict, Any, Iterator
from search_engine import search_code_chunks_with_coverage
from foundry_utils import get_chat_completions_url
DEFAULT_MODEL = "qwen2.5-coder-1.5b"

# Sorunun ayırt edici kelimelerinin en az bu kadarı kod tabanında geçmeli.
# Bunun altındaki sorular kod tabanıyla ilgisizdir; benzerlik skoru yüksek çıksa
# bile (skor, sözlükte olmayan kelimeler atıldığı için yanıltıcı olabiliyor)
# yanıt üretmeyi reddediyoruz.
MIN_QUERY_COVERAGE = 0.62

NO_MATCH_ANSWER = "I couldn't find enough relevant code in the repository to answer your question with confidence."
OFF_TOPIC_ANSWER = (
    "That topic does not appear anywhere in the indexed code, so I can't answer it from this repository. "
    "Try asking about a module, class, or function that exists in the analyzed source."
)

SYSTEM_PROMPT = (
    "You are Codetrace AI, an expert software architecture mentor. "
    "Your goal is to answer the user's question accurately based ONLY on the provided code snippets. "
    "Follow these rules:\n"
    "1. Explain WHY the code is structured this way if applicable.\n"
    "2. Highlight any design patterns used (e.g., Singleton, Factory, Dependency Injection).\n"
    "3. Keep your tone encouraging, professional, and educational for developers.\n"
    "4. If the code context does not contain the answer, strictly state that you cannot determine it from the given code."
)


def _retrieve_context(query: str, confidence_threshold: float):
    """
    Soruyla ilgili kod parçalarını arar ve LLM'e gönderilecek bağlamı hazırlar.

    İki ayrı halüsinasyon engeli var ve ikisi de gerekli:
      - benzerlik skoru: eldeki en iyi parça yeterince benziyor mu?
      - kapsama oranı  : sorunun ayırt edici kelimeleri kod tabanında var mı?
    Tek başına skora güvenmek yetmiyor; kod tabanıyla ilgisiz bir soru,
    anlamlı kelimeleri TF-IDF sözlüğünde bulunmadığı için elenince geriye kalan
    genel kelimeler üzerinden yüksek skor alabiliyor.

    Yanıt üretilmemesi gerekiyorsa nedenini belirten bir dize döner.
    """
    print(f"\n[INFO] '{query}' sorusu için kod tabanı taranıyor...")
    relevant_chunks, coverage = search_code_chunks_with_coverage(query, top_k=3)

    if coverage < MIN_QUERY_COVERAGE:
        print(f"[GUARDRAIL] Soru kod tabanının dışında (kapsama={coverage:.2f}), yanıt üretilmiyor.")
        return "off_topic"

    if not relevant_chunks or relevant_chunks[0]["score"] < confidence_threshold:
        return "no_match"

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

    return {
        "top_score": relevant_chunks[0]["score"],
        "sources": sources,
        "user_prompt": f"Code Context:\n{context_text}\n\nUser Question: {query}"
    }


def _build_payload(user_prompt: str, model_name: str, stream: bool = False) -> Dict[str, Any]:
    return {
        "model": model_name,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt}
        ],
        "temperature": 0.2,
        "max_tokens": 600,
        "stream": stream
    }


def ask_codetrace(query: str, model_name: str = DEFAULT_MODEL, confidence_threshold: float = 10.0) -> Dict[str, Any]:
    """
    RAG Akışı (tek seferde yanıt):
    1. İlgili kod parçalarını arar.
    2. Güven skorunu kontrol eder (Halüsinasyon engelleme).
    3. Mentörlük tonunda prompt hazırlar ve Foundry Local'a gönderir.
    """
    context = _retrieve_context(query, confidence_threshold)
    if isinstance(context, str):
        refusal = OFF_TOPIC_ANSWER if context == "off_topic" else NO_MATCH_ANSWER
        return {"answer": refusal, "confidence_score": 0.0, "sources": []}

    top_score = context["top_score"]
    sources = context["sources"]
    payload = _build_payload(context["user_prompt"], model_name)

    try:
        response = requests.post(get_chat_completions_url(), json=payload, timeout=180)
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
        answer = "Could not connect to Foundry Local. Start it with `foundry server start` and try again."
    except Exception as e:
        answer = f"Could not connect to Foundry Local daemon: {str(e)}"

    return {
        "answer": answer,
        "confidence_score": top_score,
        "sources": sources
    }


def ask_codetrace_stream(query: str, model_name: str = DEFAULT_MODEL, confidence_threshold: float = 10.0) -> Iterator[str]:
    """
    ask_codetrace ile aynı RAG akışı, ama yanıtı üretildiği anda parça parça
    gönderir. Böylece kullanıcı 60-90 saniye boş ekrana bakmak yerine ilk
    kelimeleri saniyeler içinde görür.

    NDJSON (her satır bir JSON) formatında akış üretir:
      {"type": "meta",  "confidence_score": .., "sources": [..]}   -- ilk satır
      {"type": "text",  "value": ".."}                             -- 0..n adet
      {"type": "done"}                                             -- son satır
    """
    context = _retrieve_context(query, confidence_threshold)

    if isinstance(context, str):
        refusal = OFF_TOPIC_ANSWER if context == "off_topic" else NO_MATCH_ANSWER
        yield json.dumps({"type": "meta", "confidence_score": 0.0, "sources": []}) + "\n"
        yield json.dumps({"type": "text", "value": refusal}) + "\n"
        yield json.dumps({"type": "done"}) + "\n"
        return

    yield json.dumps({
        "type": "meta",
        "confidence_score": context["top_score"],
        "sources": context["sources"]
    }) + "\n"

    payload = _build_payload(context["user_prompt"], model_name, stream=True)

    try:
        with requests.post(get_chat_completions_url(), json=payload, stream=True, timeout=180) as response:
            if response.status_code != 200:
                detail = response.text
                message = (
                    f"Foundry Local model '{model_name}' is not currently loaded. "
                    f"Run `foundry model load {model_name}` and try again."
                    if "is not loaded" in detail
                    else f"Error from Foundry Local daemon (Status Code: {response.status_code})\nDetails: {detail}"
                )
                yield json.dumps({"type": "text", "value": message}) + "\n"
            else:
                for line in response.iter_lines(decode_unicode=True):
                    if not line or not line.startswith("data:"):
                        continue
                    data = line[len("data:"):].strip()
                    if data == "[DONE]":
                        break
                    try:
                        chunk = json.loads(data)
                    except json.JSONDecodeError:
                        continue
                    delta = (chunk.get("choices") or [{}])[0].get("delta", {}).get("content")
                    if delta:
                        yield json.dumps({"type": "text", "value": delta}) + "\n"
    except requests.exceptions.Timeout:
        yield json.dumps({"type": "text", "value": "Foundry Local took too long to respond. The model may still be warming up — please try again."}) + "\n"
    except requests.exceptions.ConnectionError:
        yield json.dumps({"type": "text", "value": "Could not connect to Foundry Local. Start it with `foundry server start` and try again."}) + "\n"
    except Exception as e:
        yield json.dumps({"type": "text", "value": f"Could not connect to Foundry Local daemon: {str(e)}"}) + "\n"

    yield json.dumps({"type": "done"}) + "\n"


if __name__ == "__main__":
    test_query = "How does HTTP session handling work in requests?"
    response = ask_codetrace(test_query)
    
    print("\n" + "="*50)
    print(f"CONFIDENCE SCORE: %{response['confidence_score']}")
    print(f"SOURCES: {response['sources']}")
    print("="*50)
    print(f"ANSWER:\n\n{response['answer']}")
    print("="*50)
