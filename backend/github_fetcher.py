import requests

def fetch_repo_files(repo_url: str):
    """
    GitHub REST API kullanarak repodaki Python kodlarını ve Markdown dokümanlarını çeker.
    """
    clean_url = repo_url.rstrip("/").replace("https://github.com/", "")
    parts = clean_url.split("/")
    
    if len(parts) < 2:
        print("❌ Geçersiz GitHub URL formatı!")
        return []

    owner, repo = parts[0], parts[1]
    api_url = f"https://api.github.com/repos/{owner}/{repo}/git/trees/main?recursive=1"
    
    print(f"🔍 '{owner}/{repo}' reposu taranıyor...")
    
    headers = {"User-Agent": "Codetrace-App"}
    response = requests.get(api_url, headers=headers)
    
    if response.status_code != 200:
        api_url = f"https://api.github.com/repos/{owner}/{repo}/git/trees/master?recursive=1"
        response = requests.get(api_url, headers=headers)

    if response.status_code != 200:
        print(f"❌ Hata: Repo çekilemedi (Status Code: {response.status_code})")
        return []

    data = response.json()
    tree = data.get("tree", [])
    
    # Kod dosyalarını (.py) VE dokümantasyon dosyalarını (.md) filtrele
    valid_files = [
        item["path"] for item in tree 
        if item["type"] == "blob" and (item["path"].endswith(".py") or item["path"].endswith(".md"))
    ]
    
    print(f"✅ Toplam {len(valid_files)} adet analiz edilebilir dosya bulundu (Kod & Doküman):\n")
    for file in valid_files[:10]:
        print(f" 📄 {file}")
        
    if len(valid_files) > 10:
        print(f" ... ve {len(valid_files) - 10} dosya daha.")

    return valid_files

if __name__ == "__main__":
    test_repo = "https://github.com/psf/requests"
    fetch_repo_files(test_repo)
