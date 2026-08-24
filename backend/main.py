from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr
from typing import Dict, Any
import sqlite3
from pipeline import index_github_repository
from rag_engine import ask_codetrace, ask_codetrace_stream, DEFAULT_MODEL
from diagram_generator import generate_architecture_diagram, get_diagram_node_details, get_architecture_graph
from readme_generator import generate_repo_readme
from indexer import DB_PATH, get_file_content as get_indexed_file_content
from auth import register_user, login_user, get_user_by_token, revoke_session
from foundry_utils import ensure_model_loaded

app = FastAPI(
    title="Codetrace AI API",
    description="Privacy-First Local RAG Backend for GitHub Repository Analysis",
    version="1.0.0"
)


@app.on_event("startup")
def load_foundry_model_on_startup():
    """
    Make sure the default Foundry Local model is loaded before serving traffic.
    Does nothing if it is already in memory.
    """
    ensure_model_loaded(DEFAULT_MODEL)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


bearer_scheme = HTTPBearer(auto_error=False)


def require_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme)
) -> Dict[str, Any]:
    """
    Session check for protected endpoints.

    The client's own "signed in" flag is never trusted: the token is matched
    against the stored session on every request.
    """
    token = credentials.credentials if credentials else None
    user = get_user_by_token(token)
    if not user:
        raise HTTPException(status_code=401, detail="A valid session is required. Please sign in.")
    return user


class AnalyzeRequest(BaseModel):
    repo_url: str


class AskRequest(BaseModel):
    query: str


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    name: str = ""


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


@app.get("/")
def read_root():
    return {"status": "online", "service": "Codetrace AI RAG API", "version": "1.0.0"}


@app.post("/api/analyze")
def analyze_repository(request: AnalyzeRequest, user: Dict[str, Any] = Depends(require_user)):
    if not request.repo_url:
        raise HTTPException(status_code=400, detail="repo_url is required.")
    try:
        result = index_github_repository(request.repo_url)
        return {
            "status": "success",
            "message": f"Indexed '{request.repo_url}' successfully.",
            "repo_url": request.repo_url,
            "stars": result.get("stars", 0),
            "total_chunks": result.get("total_chunks", 0),
            "file_list": result.get("file_list", []),
            "mermaid_code": result.get("mermaid_code", ""),
            "graph": get_architecture_graph(),
            "node_details": get_diagram_node_details()
        }
    except Exception as e:
        # Details go to the log, not the browser: file paths and stack frames
        # should not leak to the client.
        print(f"[ERROR] Indexing failed: {e}")
        raise HTTPException(status_code=500, detail="Could not index the repository. Check the server logs.")


@app.post("/api/ask")
def ask_question(request: AskRequest, user: Dict[str, Any] = Depends(require_user)):
    if not request.query:
        raise HTTPException(status_code=400, detail="query is required.")
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
        print(f"[ERROR] Query failed: {e}")
        raise HTTPException(status_code=500, detail="Could not answer the query. Check the server logs.")


@app.post("/api/ask-stream")
def ask_question_stream(request: AskRequest, user: Dict[str, Any] = Depends(require_user)):
    """
    Same answer as /api/ask, but streamed token by token so the client sees
    the first words within seconds.
    """
    if not request.query:
        raise HTTPException(status_code=400, detail="query is required.")
    return StreamingResponse(
        ask_codetrace_stream(request.query),
        media_type="application/x-ndjson",
        headers={"X-Accel-Buffering": "no", "Cache-Control": "no-cache"}
    )


@app.get("/api/diagram")
def get_architecture_diagram(user: Dict[str, Any] = Depends(require_user)):
    try:
        return generate_architecture_diagram()
    except Exception as e:
        print(f"[ERROR] Diagram generation failed: {e}")
        raise HTTPException(status_code=500, detail="Could not generate the diagram. Check the server logs.")


@app.post("/api/generate-readme")
def generate_readme(user: Dict[str, Any] = Depends(require_user)):
    try:
        result = generate_repo_readme()
    except Exception as e:
        print(f"[ERROR] README generation failed: {e}")
        raise HTTPException(status_code=500, detail="Could not generate the README. Check the server logs.")

    if result.get("status") != "success":
        # Nothing indexed yet is a client mistake, not a server failure.
        raise HTTPException(status_code=400, detail=result.get("message", "Could not generate the README"))
    return result


@app.post("/api/register")
def register(request: RegisterRequest):
    if not request.password:
        raise HTTPException(status_code=400, detail="Email and password are required.")
    email = request.email.strip().lower()
    name = request.name.strip() or email.split("@")[0]
    result = register_user(email, request.password, name)
    if result["status"] == "error":
        raise HTTPException(status_code=400, detail=result["message"])
    return result


@app.post("/api/login")
def login(request: LoginRequest):
    if not request.password:
        raise HTTPException(status_code=400, detail="Email and password are required.")
    result = login_user(request.email.strip().lower(), request.password)
    if result["status"] == "error":
        raise HTTPException(status_code=401, detail=result["message"])
    return result


@app.get("/api/me")
def read_current_user(user: Dict[str, Any] = Depends(require_user)):
    """
    Confirm the client's stored token is still valid, so a reloaded page
    cannot show a signed-in shell without a real session behind it.
    """
    return {"status": "success", "user": user}


@app.post("/api/logout")
def logout(credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme)):
    if credentials:
        revoke_session(credentials.credentials)
    return {"status": "success"}


@app.get("/api/file-content")
def get_file_content(path: str, user: Dict[str, Any] = Depends(require_user)):
    """
    Prefer the complete raw file captured during indexing. If that is missing,
    reassemble what is available from the AST chunks. If neither exists, say so
    plainly -- never fabricate code.
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
            "content": f"# No indexed record found for '{path}'."
        }
    except Exception as e:
        print(f"[ERROR] Could not read file content: {e}")
        raise HTTPException(status_code=500, detail="Could not read the file content. Check the server logs.")
