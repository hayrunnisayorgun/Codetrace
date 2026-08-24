from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from typing import List, Dict, Any, Tuple
from indexer import get_all_chunks, init_db, clear_db, save_chunks_to_db, DB_PATH
from ast_parser import parse_python_code


# Question-shaped words that carry no topic. They rarely appear in code, so
# counting them as "unknown" would reject genuine questions ("Explain the
# HTTPAdapter class" failed purely because 'explain' is absent from the code).
# Counting them as known would rescue unrelated ones just as unfairly, so they
# are excluded from the calculation entirely.
QUESTION_WORDS = frozenset({
    "explain", "describe", "tell", "show", "give", "list", "summarize", "walk",
    "what", "how", "why", "where", "which", "who", "when", "does", "did", "doing",
    "use", "used", "uses", "using", "work", "works", "working", "handle", "handles",
    "handled", "implement", "implemented", "implementation", "library", "package",
    "module", "code", "codebase", "project", "repository", "repo", "here", "this",
    "that", "these", "those", "please", "help", "me", "you", "it", "its", "the",
    "and", "for", "with", "about", "inside", "within",
})


def compute_query_coverage(query: str, vectorizer: TfidfVectorizer) -> float:
    """
    Score 0..1 for how much of a question's DISTINCTIVE vocabulary actually
    occurs in the indexed code.

    Why this is needed: TF-IDF silently discards terms outside its vocabulary.
    So "How does this library handle GraphQL subscriptions?" lost the two words
    carrying its meaning ('graphql', 'subscriptions') and scored HIGH on the
    generic remainder ('library', 'handle') -- the hallucination guard failed
    exactly when it mattered most.

    Terms are weighted by IDF, and a term absent from the code is treated as
    maximally distinctive, so it drives the score down hard.
    """
    terms = [t for t in vectorizer.build_analyzer()(query) if t not in QUESTION_WORDS]
    if not terms:
        # No topical words at all ("how does this work?"); nothing to verify,
        # so leave the decision to the similarity score.
        return 1.0

    vocabulary = vectorizer.vocabulary_
    idf = vectorizer.idf_
    max_idf = float(idf.max())

    known_weight = 0.0
    total_weight = 0.0
    for term in terms:
        if term in vocabulary:
            weight = float(idf[vocabulary[term]])
            known_weight += weight
        else:
            weight = max_idf
        total_weight += weight

    return known_weight / total_weight if total_weight else 0.0


def search_code_chunks_with_coverage(query: str, top_k: int = 3, db_path: str = DB_PATH) -> Tuple[List[Dict[str, Any]], float]:
    """
    Return the top_k most similar chunks together with the question's
    vocabulary coverage.
    """
    chunks = get_all_chunks(db_path)

    if not chunks:
        print("[WARNING] Nothing indexed to search.")
        return [], 0.0

    corpus = [f"{c['name']} {c['code_content']}" for c in chunks]

    vectorizer = TfidfVectorizer(stop_words='english')
    corpus_vectors = vectorizer.fit_transform(corpus)

    query_vector = vectorizer.transform([query])
    similarities = cosine_similarity(query_vector, corpus_vectors)[0]
    coverage = compute_query_coverage(query, vectorizer)

    ranked_indices = similarities.argsort()[::-1][:top_k]
    results = []
    for idx in ranked_indices:
        score = similarities[idx]
        chunk = chunks[idx]
        chunk["score"] = round(float(score) * 100, 2)
        results.append(chunk)

    return results, coverage


def search_code_chunks(query: str, top_k: int = 3, db_path: str = DB_PATH) -> List[Dict[str, Any]]:
    """
    Find the top_k chunks most similar to the question via TF-IDF cosine similarity.
    """
    results, _ = search_code_chunks_with_coverage(query, top_k, db_path)
    return results

if __name__ == "__main__":
    init_db()
    clear_db()

    sample_code = """
def connect_to_database():
    print("Database connection opened")

def read_user_profile(user_id):
    return {"id": user_id, "name": "Hayrunnisa"}

class AuthSystem:
    def login_with_password(self, username, password):
        print("Logging in user...")
        return True
"""
    chunks = parse_python_code(sample_code, "app_services.py")
    save_chunks_to_db(chunks)

    query = "database connection open"
    print(f"\n[INFO] Question: '{query}'")

    results = search_code_chunks(query, top_k=2)

    print("\n[RESULTS] Most relevant chunks:")
    for r in results:
        print(f"\n[SCORE] {r['score']}% | [{r['type'].upper()}] {r['name']} ({r['file_path']}: lines {r['start_line']}-{r['end_line']})")
        print(f"```{r['code_content']}```")