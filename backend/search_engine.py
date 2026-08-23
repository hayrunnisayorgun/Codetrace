from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from typing import List, Dict, Any, Tuple
from indexer import get_all_chunks, init_db, clear_db, save_chunks_to_db, DB_PATH
from ast_parser import parse_python_code


# Soru kalıbına ait, konu taşımayan kelimeler. Bunlar kod içinde nadiren geçtiği
# için kapsama hesabında "bilinmeyen" sayılırsa gerçek sorular haksızca elenir
# ("Explain the HTTPAdapter class" -> 'explain' kodda yok diye reddedilirdi).
# Aynı şekilde numaratörde sayılırlarsa da ilgisiz soruları haksızca kurtarırlar,
# bu yüzden hesabın tamamen dışında tutuluyorlar.
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
    Sorudaki AYIRT EDİCİ kelimelerin ne kadarının kod tabanında gerçekten
    geçtiğini 0..1 aralığında ölçer.

    Neden gerekli: TF-IDF, sözlüğünde olmayan kelimeleri sessizce atar. Bu yüzden
    kod tabanıyla hiç ilgisi olmayan bir soru ("How does this library handle
    GraphQL subscriptions?") anlamı taşıyan kelimelerini ('graphql',
    'subscriptions') kaybedip geriye kalan genel kelimeler ('library', 'handle')
    üzerinden YÜKSEK benzerlik skoru alabiliyordu -- yani halüsinasyon engeli
    tam da en çok gerektiği anda devre dışı kalıyordu.

    Kelimeleri IDF ağırlığıyla tartıyoruz: kod tabanında hiç geçmeyen bir kelime
    mümkün olan en ayırt edici kelimedir, bu yüzden en yüksek ağırlığı alır ve
    kapsama oranını sertçe düşürür.
    """
    terms = [t for t in vectorizer.build_analyzer()(query) if t not in QUESTION_WORDS]
    if not terms:
        # Soruda hiç konu kelimesi yok ("how does this work?"); kontrol edecek bir
        # şey kalmadığından kararı benzerlik skoruna bırakıyoruz.
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
    En benzer top_k kod parçasını ve sorunun kod tabanı sözlüğüyle kapsama
    oranını birlikte döner.
    """
    chunks = get_all_chunks(db_path)

    if not chunks:
        print("[WARNING] Veritabanında aranacak kayıt bulunamadı.")
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
    Kullanıcının sorusuna en benzeyen top_k adet kod parçasını TF-IDF ve Kosinüs Benzerliği ile bulur.
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
    print(f"\n[INFO] Sorulan Soru: '{query}'")

    results = search_code_chunks(query, top_k=2)

    print("\n[RESULTS] ARAMA SONUÇLARI (En Alakalı Parçalar):")
    for r in results:
        print(f"\n[SCORE] Güven Skoru: %{r['score']} | [{r['type'].upper()}] {r['name']} ({r['file_path']}: Satır {r['start_line']}-{r['end_line']})")
        print(f"```{r['code_content']}```")