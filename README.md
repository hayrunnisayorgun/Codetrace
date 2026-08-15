# Codetrace — AI Codebase & Architecture Auditor

**Codetrace** is a local-first, RAG-powered developer tool that ingests any public GitHub repository live, indexes its code with a custom AST-based chunking pipeline, and lets you explore the codebase through natural-language Q&A, an auto-generated architecture diagram, and an AI-generated README — all running on **Microsoft Foundry Local**, with zero code ever leaving your machine.

Built as part of Microsoft's 2026 AI Summer Internship Program (Foundry Local + RAG track).

---

## Why Codetrace

Understanding an unfamiliar codebase is one of the most time-consuming parts of a developer's job — new hires spend weeks just figuring out "where does X happen" or "why is this structured this way." Codetrace turns that process into a conversation: paste a repo URL, and start asking questions.

Unlike generic chat assistants, Codetrace never relies on the model's memorized knowledge of a library. Every answer is grounded exclusively in the code it actually indexed from *your* repository — with a visible confidence score and exact file/line citations for every response.

---

## Key Features

- **⚡ Live Repository Ingestion** — Paste any public GitHub repo URL. No cloning, no ZIP downloads; files are fetched directly via the GitHub REST API.

- **🧩 AST-Based Code Chunking** — Python files are parsed with the `ast` module into function-, class-, and method-level chunks (e.g. `AuthSystem.login`), instead of naive line-based splitting — giving far more precise retrieval.

- **🔍 TF-IDF Retrieval with Confidence Scoring** — Every answer is paired with a transparent similarity score, so you know exactly how much to trust it — not just a plausible-sounding answer.

- **🛡️ Two-Layer Hallucination Guard** — A strict system prompt plus code-level post-processing ensures the model never falls back on its own pretrained knowledge of popular libraries (e.g. inventing `pip install` commands that aren't actually documented in the indexed code).

- **🎓 Junior-Friendly Mentor Mode** — Answers don't just state facts — they explain *why* the code is structured that way and call out recognizable design patterns, aimed at helping junior developers actually learn from the codebase.

- **🎨 Auto-Generated Architecture Diagrams** — A Mermaid.js dependency graph is built automatically from regex-based cross-file reference detection, visualizing how modules actually depend on each other.

- **📝 AI-Generated README Drafts** — Generates a concise, fact-grounded README summary of any indexed repository, with the same hallucination guard applied.

- **🔒 100% Local Inference** — Powered by Microsoft Foundry Local running `qwen2.5-coder-1.5b` on-device. No API keys, no cloud calls, no data leaves your machine.

---

## Architecture

```
GitHub Repo URL
      │
      ▼
┌─────────────────┐     ┌──────────────────┐     ┌───────────────────┐
│  GitHub Fetcher  │────▶│   AST Parser      │────▶│  SQLite Indexer   │
│  (REST API)      │     │  (function/class/  │     │  (chunk storage)  │
└─────────────────┘     │   method chunking) │     └───────────────────┘
                         └──────────────────┘               │
                                                            ▼
                                                    ┌───────────────────┐
                                                    │  TF-IDF Search     │
                                                    │  Engine             │
                                                    │  (cosine similarity)│
                                                    └───────────────────┘
                                                            │
                                                            ▼
┌─────────────────┐     ┌──────────────────┐     ┌───────────────────┐
│  Mermaid.js       │◀────│  FastAPI REST     │────▶│  Foundry Local      │
│  Diagram Generator│     │  API (/analyze,    │     │  RAG Engine          │
└─────────────────┘     │   /ask, /generate-  │     │  (grounded Q&A)      │
                         │   readme)           │     └───────────────────┘
                         └──────────────────┘
                                   │
                                   ▼
                         ┌──────────────────┐
                         │  React + Tailwind │
                         │  Dark UI (IDE-     │
                         │  inspired)          │
                         └──────────────────┘
```

---

## Tech Stack

| Layer | Technology |
|---|---|
| LLM Inference | Microsoft Foundry Local (`qwen2.5-coder-1.5b`) |
| Backend | Python, FastAPI |
| Code Parsing | Python `ast` module |
| Retrieval | scikit-learn (TF-IDF + cosine similarity) |
| Storage | SQLite |
| Diagram Generation | Mermaid.js (regex-based dependency extraction) |
| Frontend | React (Vite) + Tailwind CSS + lucide-react |

---

## Getting Started

### Prerequisites
- [Microsoft Foundry Local](https://learn.microsoft.com/en-us/azure/ai-foundry/foundry-local/) installed and running
- Python 3.10+
- Node.js 18+

### Backend

```bash
cd backend
python -m venv venv
venv\Scripts\activate        # Windows
pip install -r requirements.txt

foundry service start
foundry model load qwen2.5-coder-1.5b

uvicorn main:app --reload
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173`, paste a public GitHub repo URL (e.g. `https://github.com/psf/requests`), and click **Analyze Repository**.

---

## Design Decisions & Trade-offs

A few deliberate engineering calls worth noting:

- **TF-IDF over embeddings:** Chosen for speed and zero extra dependencies at this scale (hundreds of chunks). For much larger codebases, a proper embedding-based vector store would be the natural next step.
- **`qwen2.5-coder-1.5b` over the 7B variant:** The development machine's limited RAM made the 7B model unreliable for consistent local inference. The 1.5B model was benchmarked and found to produce accurate, grounded answers at a fraction of the latency — a conscious latency/quality trade-off appropriate for a real-time chat interface.
- **Single-repo indexing:** The current scope re-indexes on each new analysis rather than maintaining multiple repos simultaneously — a deliberate MVP boundary, not a limitation of the underlying architecture.

---

## Roadmap

- [ ] Multi-language support beyond Python (JS/TS, Go)
- [ ] Persistent multi-repo indexing
- [ ] Embedding-based retrieval for large-scale codebases
- [ ] Adjustable fast/deep inference mode (lightweight vs. larger local model)

---

## Author

Built by **Hayrunnisa Yorgun** as part of Microsoft's 2026 AI Summer Internship Program.
