from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from typing import List, Dict, Any
from indexer import get_all_chunks, init_db, clear_db, save_chunks_to_db
from ast_parser import parse_python_code


def search_code_chunks(query: str, top_k: int = 3, db_path: str = "codetrace.db") -> List[Dict[str, Any]]:
    """
    Kullanıcının sorusuna en benzeyen top_k adet kod parçasını TF-IDF ve Kosinüs Benzerliği ile bulur.
    """
    chunks = get_all_chunks(db_path)

    if not chunks:
        print("⚠️ Veritabanında aranacak kayıt bulunamadı.")
        return []

    corpus = [f"{c['name']} {c['code_content']}" for c in chunks]

    # Not: stop_words='english' sadece İngilizce dolgu kelimelerini filtreler.
    # Kod tabanı çoğunlukla İngilizce (fonksiyon adları, kütüphane isimleri) olduğu için
    # bu proje kapsamında yeterli — Türkçe yorum ağırlıklı bir repo test edilirse
    # bu satır kaldırılıp stop word filtresi devre dışı bırakılabilir.
    vectorizer = TfidfVectorizer(stop_words='english')
    corpus_vectors = vectorizer.fit_transform(corpus)

    query_vector = vectorizer.transform([query])
    similarities = cosine_similarity(query_vector, corpus_vectors)[0]

    ranked_indices = similarities.argsort()[::-1][:top_k]
    results = []
    for idx in ranked_indices:
        score = similarities[idx]
        chunk = chunks[idx]
        chunk["score"] = round(float(score) * 100, 2)
        results.append(chunk)

    return results


if __name__ == "__main__":
    init_db()
    clear_db()

    sample_code = """
def connect_to_database():
    # Database baglantisi saglar ve verileri okur
    print("Database connection opened")

def read_user_profile(user_id):
    # Kullanici profil bilgilerini getirir
    return {"id": user_id, "name": "Hayrunnisa"}

class AuthSystem:
    def login_with_password(self, username, password):
        # Kullanici giris yapma fonksiyonu
        print("Logging in user...")
        return True
"""
    chunks = parse_python_code(sample_code, "app_services.py")
    save_chunks_to_db(chunks)

    query = "database connection open"
    print(f"\n❓ Sorulan Soru: '{query}'")

    results = search_code_chunks(query, top_k=2)

    print("\n🎯 ARAMA SONUÇLARI (En Alakalı Parçalar):")
    for r in results:
        print(f"\n🛡️ Güven Skoru: %{r['score']} | [{r['type'].upper()}] {r['name']} ({r['file_path']}: Satır {r['start_line']}-{r['end_line']})")
        print(f"```{r['code_content']}```")