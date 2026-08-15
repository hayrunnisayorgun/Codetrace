from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict, Any
from pipeline import index_github_repository
from rag_engine import ask_codetrace
from diagram_generator import generate_architecture_diagram

app = FastAPI(
    title="Codetrace AI API",
    description="Privacy-First Local RAG Backend for GitHub Repository Analysis",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
    Canlı GitHub reposunu sıfırdan indirir, AST ile parçalar, SQLite'a indeksler ve otomatik Mermaid diyagramı döner.
    """
    if not request.repo_url:
        raise HTTPException(status_code=400, detail="repo_url parametresi zorunludur.")
    
    try:
        result = index_github_repository(request.repo_url)
        return {
            "status": "success",
            "message": f"'{request.repo_url}' reposu başarıyla indekslendi.",
            "repo_url": request.repo_url,
            "total_chunks": result.get("total_chunks", 0),
            "mermaid_code": result.get("mermaid_code", "")
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

@app.get("/api/diagram")
def get_architecture_diagram():
    """
    İndekslenmiş repo için otomatik Mermaid.js mimari bağımlılık şemasını döner.
    """
    try:
        result = generate_architecture_diagram()
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Diyagram üretme hatası: {str(e)}")
