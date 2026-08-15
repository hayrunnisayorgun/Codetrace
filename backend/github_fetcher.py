import os
import requests

def fetch_repo_files(repo_url: str):
    """
    GitHub REST API kullanarak repodaki Python kodlarını ve Markdown dokümanlarını çeker.
    .env içinde GITHUB_TOKEN varsa limiti 60'tan 5000'e çıkarır.
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
    
    # Opsiyonel GitHub Token Kontrolü
    github_token = os.getenv("GITHUB_TOKEN")
    if github_token:
        headers["Authorization"] = f"Bearer {github_token}"

    response = requests.get(api_url, headers=headers)
    
    if response.status_code != 200:
        api_url = f"https://api.github.com/repos/{owner}/{repo}/git/trees/master?recursive=1"
        response = requests.get(api_url, headers=headers)

    if response.status_code != 200:
        print(f"❌ Hata: Repo çekilemedi (Status Code: {response.status_code})")
        return []

    data = response.json()
    tree = data.get("tree", [])
    
    valid_files = [
        item["path"] for item in tree 
        if item["type"] == "blob" and (item["path"].endswith(".py") or item["path"].endswith(".md"))
    ]

    return valid_files

if __name__ == "__main__":
    test_repo = "https://github.com/psf/requests"
    files = fetch_repo_files(test_repo)
    print(f"✅ Toplam {len(files)} dosya bulundu.")
