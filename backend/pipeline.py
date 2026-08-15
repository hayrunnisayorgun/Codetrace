import requests
from typing import List, Dict, Any
from github_fetcher import fetch_repo_files
from ast_parser import parse_python_code
from indexer import init_db, clear_db, save_chunks_to_db
from rag_engine import ask_codetrace

def is_relevant_file(file_path: str) -> bool:
    """Docs, test, config gibi düşük değerli dosyaları filtreler."""
    ignore_patterns = ["docs/", "test", "setup.py", "__version__.py", "conf.py"]
    return not any(pattern in file_path.lower() for pattern in ignore_patterns)

def fetch_raw_file_content(owner: str, repo: str, branch: str, file_path: str) -> str:
    """
    GitHub'dan dosyanın ham kod metnini (raw text) indirir.
    """
    raw_url = f"https://raw.githubusercontent.com/{owner}/{repo}/{branch}/{file_path}"
    response = requests.get(raw_url)
    if response.status_code == 200:
        return response.text
    return ""

def index_github_repository(repo_url: str):
    """
    Canlı GitHub reposunu sıfırdan indirir, akıllı filtreleme ile AST parçalarına böler ve SQLite'a indeksler.
    """
    clean_url = repo_url.rstrip("/").replace("https://github.com/", "")
    parts = clean_url.split("/")
    if len(parts) < 2:
        print("❌ Geçersiz GitHub URL formatı!")
        return

    owner, repo = parts[0], parts[1]
    
    print(f"\n🚀 '{owner}/{repo}' reposu için uçtan uca indeksleme başlatılıyor...")
    
    # 1. Veritabanını temizle ve hazırla
    init_db()
    clear_db()

    # 2. Repo dosya listesini çek
    file_paths = fetch_repo_files(repo_url)
    
    # Akıllı dosya filtreleme
    python_files = [f for f in file_paths if f.endswith(".py") and is_relevant_file(f)]
    
    total_chunks = []
    print(f"\n⚙️ {len(python_files)} adet ana kaynak kod dosyası indiriliyor ve AST ile ayrıştırılıyor...")
    
    # İlk 15 önemli kaynak kod dosyasını indeksleyelim
    for file_path in python_files[:15]:
        content = fetch_raw_file_content(owner, repo, "main", file_path)
        if not content:
            content = fetch_raw_file_content(owner, repo, "master", file_path)
            
        if content:
            chunks = parse_python_code(content, file_path)
            total_chunks.extend(chunks)
            print(f" └─ 📄 {file_path} -> {len(chunks)} chunk çıkarıldı.")

    # 3. Tüm parçaları veritabanına kaydet
    save_chunks_to_db(total_chunks)
    print(f"\n✅ REPO İNDEKSLEME TAMAMLANDI! Toplam {len(total_chunks)} kod parçası veritabanına yazıldı.")

if __name__ == "__main__":
    # Canlı GitHub Reposu İndeksleme Testi
    test_repo = "https://github.com/psf/requests"
    index_github_repository(test_repo)
    
    # Canlı Soru Sorma Testi
    query = "How does HTTP session handling work in requests?"
    response = ask_codetrace(query)
    
    print("\n" + "="*50)
    print(f"🛡️ CONFIDENCE SCORE: %{response['confidence_score']}")
    print(f"📌 SOURCES: {response['sources']}")
    print("="*50)
    print(f"🤖 CODETRACE AI MENTOR ANSWER:\n\n{response['answer']}")
    print("="*50)
