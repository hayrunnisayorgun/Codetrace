from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import sqlite3
from pipeline import index_github_repository
from rag_engine import ask_codetrace, DEFAULT_MODEL
from diagram_generator import generate_architecture_diagram, get_diagram_node_details
from readme_generator import generate_repo_readme
from indexer import DB_PATH, get_file_content as get_indexed_file_content
from auth import register_user, login_user
from foundry_utils import ensure_model_loaded

app = FastAPI(
    title="Codetrace AI API",
    description="Privacy-First Local RAG Backend for GitHub Repository Analysis",
    version="1.0.0"
)


@app.on_event("startup")
def load_foundry_model_on_startup():
    """
    Backend ayağa kalkarken Foundry Local'daki varsayılan modelin belleğe
    yüklü olduğundan emin olur. Model zaten yüklüyse hiçbir şey yapmaz.
    """
    ensure_model_loaded(DEFAULT_MODEL)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class AnalyzeRequest(BaseModel):
    repo_url: str


class AskRequest(BaseModel):
    query: str


class RegisterRequest(BaseModel):
    email: str
    password: str
    name: str = ""


class LoginRequest(BaseModel):
    email: str
    password: str


@app.get("/")
def read_root():
    return {"status": "online", "service": "Codetrace AI RAG API", "version": "1.0.0"}


@app.post("/api/analyze")
def analyze_repository(request: AnalyzeRequest):
    if not request.repo_url:
        raise HTTPException(status_code=400, detail="repo_url parametresi zorunludur.")
    try:
        result = index_github_repository(request.repo_url)
        return {
            "status": "success",
            "message": f"'{request.repo_url}' reposu başarıyla indekslendi.",
            "repo_url": request.repo_url,
            "stars": result.get("stars", 0),
            "total_chunks": result.get("total_chunks", 0),
            "file_list": result.get("file_list", []),
            "mermaid_code": result.get("mermaid_code", ""),
            "readme_markdown": result.get("readme_markdown", ""),
            "node_details": get_diagram_node_details()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"İndeksleme hatası: {str(e)}")


@app.post("/api/ask")
def ask_question(request: AskRequest):
    if not request.query:
        raise HTTPException(status_code=400, detail="query parametresi zorunludur.")
    try:
        result = ask_codetrace(request.query)
        return {
            "status": "success",
            "query": request.query,
            "answer": result["answer"],
            "confidence_score": result["confidence_score"],
            "sources": result["sources"]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Sorgulama hatası: {str(e)}")


@app.get("/api/diagram")
def get_architecture_diagram():
    try:
        return generate_architecture_diagram()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Diyagram üretme hatası: {str(e)}")


@app.post("/api/generate-readme")
def generate_readme():
    try:
        result = generate_repo_readme()
        if result.get("status") == "success":
            return result
        raise HTTPException(status_code=500, detail=result.get("message", "README üretilemedi"))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"README üretim hatası: {str(e)}")


@app.post("/api/register")
def register(request: RegisterRequest):
    if not request.email or not request.password:
        raise HTTPException(status_code=400, detail="E-posta ve şifre zorunludur.")
    name = request.name.strip() or request.email.split("@")[0]
    result = register_user(request.email.strip().lower(), request.password, name)
    if result["status"] == "error":
        raise HTTPException(status_code=400, detail=result["message"])
    return result


@app.post("/api/login")
def login(request: LoginRequest):
    if not request.email or not request.password:
        raise HTTPException(status_code=400, detail="E-posta ve şifre zorunludur.")
    result = login_user(request.email.strip().lower(), request.password)
    if result["status"] == "error":
        raise HTTPException(status_code=401, detail=result["message"])
    return result


@app.get("/api/file-content")
def get_file_content(path: str):
    """
    Öncelikle GitHub'dan indekslenirken kaydedilen TAM ham dosya içeriğini döner.
    Ham içerik yoksa, veritabanındaki AST chunk'larından birleştirerek döner.
    Hiçbiri yoksa dürüstçe 'bulunamadı' der -- ASLA sahte/uydurma kod üretmez.
    """
    try:
        raw_content = get_indexed_file_content(path)
        if raw_content:
            return {"status": "success", "file_path": path, "content": raw_content}

        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT name, type, start_line, end_line, code_content FROM code_chunks WHERE file_path LIKE ?",
            (f"%{path}%",)
        )
        rows = cursor.fetchall()
        conn.close()

        if rows:
            combined = "\n\n".join(
                [f"# Component: {r[0]} ({r[1]})\n# Lines {r[2]}-{r[3]}\n{r[4]}" for r in rows]
            )
            return {"status": "success", "file_path": path, "content": combined}

        return {
            "status": "not_found",
            "file_path": path,
            "content": f"# '{path}' için indekslenmiş bir kayıt bulunamadı."
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Dosya içeriği alınamadı: {str(e)}")
