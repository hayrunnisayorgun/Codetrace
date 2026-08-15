from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict, Any
from pipeline import index_github_repository
from rag_engine import ask_codetrace

app = FastAPI(
    title="Codetrace AI API",
    description="Privacy-First Local RAG Backend for GitHub Repository Analysis",
    version="1.0.0"
)

# Frontend arayüzünün (UI) sorunsuz haberleşmesi için CORS izni
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# İstek Şablonları (Pydantic Models)
class AnalyzeRequest(BaseModel):
    repo_url: str

class AskRequest(BaseModel):
    query: str

@app.get("/")
def read_root():
    return {
        "status": "online",
        "service": "Codetrace AI RAG API",
        "version": "1.0.0"
    }

@app.post("/api/analyze")
def analyze_repository(request: AnalyzeRequest):
    """
    Canlı GitHub reposunu sıfırdan indirir, AST ile parçalar ve SQLite'a indeksler.
    """
    if not request.repo_url:
        raise HTTPException(status_code=400, detail="repo_url parametresi zorunludur.")
    
    try:
        index_github_repository(request.repo_url)
        return {
            "status": "success",
            "message": f"'{request.repo_url}' reposu başarıyla indekslendi.",
            "repo_url": request.repo_url
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"İndeksleme hatası: {str(e)}")

@app.post("/api/ask")
def ask_question(request: AskRequest):
    """
    Kullanıcının sorusunu alır, RAG motoru ile yerel LLM'den cevap üretir.
    """
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
