import requests
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, Any
from github_fetcher import fetch_repo_files, fetch_repo_metadata
from ast_parser import parse_python_code
from indexer import init_db, clear_db, save_chunks_to_db, save_file_content
from diagram_generator import generate_architecture_diagram


def is_relevant_file(file_path: str) -> bool:
    """
    Skip tests, docs and examples so indexing focuses on the actual source.
    """
    path_lower = file_path.lower()
    ignore_patterns = ["docs_src/", "docs/", "tests/", "test/", "examples/", "benchmarks/", "setup.py", "__version__.py", "conf.py"]
    return not any(pattern in path_lower for pattern in ignore_patterns)

def fetch_raw_file_content(owner: str, repo: str, branch: str, file_path: str) -> str:
    """
    Fetch a single file's contents through the GitHub raw endpoint.
    """
    raw_url = f"https://raw.githubusercontent.com/{owner}/{repo}/{branch}/{file_path}"
    response = requests.get(raw_url)
    if response.status_code == 200:
        return response.text
    return ""

def index_github_repository(repo_url: str) -> Dict[str, Any]:
    """
    Fetch a live GitHub repository, split it into AST chunks, store them in
    SQLite, read the star count, and build the architecture diagram.

    The README is deliberately not generated here: writing it with the LLM took
    ~160s on its own, all of it before the user could see the diagram. The
    client calls /api/generate-readme separately once indexing returns.
    """
    clean_url = repo_url.rstrip("/").replace("https://github.com/", "")
    parts = clean_url.split("/")
    if len(parts) < 2:
        return {"status": "error", "message": "Invalid GitHub URL format"}

    owner, repo = parts[0], parts[1]
    repo_name = f"{owner}/{repo}"
    metadata = fetch_repo_metadata(owner, repo)
    stars_count = metadata.get("stars", 0)

    init_db()
    clear_db()

    file_paths = fetch_repo_files(repo_url)
    python_files = [f for f in file_paths if f.endswith(".py") and is_relevant_file(f)]

    if not python_files:
        python_files = [f for f in file_paths if f.endswith(".py")]

    total_chunks = []
    processed_files = []

    selected_files = python_files[:15]

    def _download(file_path: str):
        content = fetch_raw_file_content(owner, repo, "main", file_path)
        if not content:
            content = fetch_raw_file_content(owner, repo, "master", file_path)
        return file_path, content

    # Downloaded in parallel: fetching them one at a time meant a separate
    # round trip per file and cost ~12s by itself.
    with ThreadPoolExecutor(max_workers=8) as executor:
        downloaded = dict(executor.map(_download, selected_files))

    # Processed in repository order so the output stays deterministic.
    for file_path in selected_files:
        content = downloaded.get(file_path)
        if content:
            save_file_content(file_path, content)
            chunks = parse_python_code(content, file_path)
            total_chunks.extend(chunks)
            processed_files.append(file_path)

    save_chunks_to_db(total_chunks)

    diagram_result = generate_architecture_diagram()

    return {
        "status": "success",
        "repo_name": repo_name,
        "stars": stars_count,
        "total_chunks": len(total_chunks),
        "total_files": len(processed_files),
        "file_list": processed_files,
        "mermaid_code": diagram_result.get("mermaid_code", "")
    }
