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

- **🛡️ Three-Layer Hallucination Guard** — Before the model is called at all, a question is checked against the indexed vocabulary: terms that never appear in the code count against it, so asking a `requests` index about "GraphQL subscriptions" is refused outright rather than answered from the model's own memory. Retrieval similarity is the second gate, and a strict system prompt is the third.

- **🎓 Junior-Friendly Mentor Mode** — Answers don't just state facts — they explain *why* the code is structured that way and call out recognizable design patterns, aimed at helping junior developers actually learn from the codebase.

- **🎨 Auto-Generated Architecture Diagrams** — A Mermaid.js dependency graph built from the repository's real `import` statements, parsed with `ast`. Files are grouped into architecture layers that start collapsed and expand on click, and each box shows only its heaviest dependency — so the diagram stays readable instead of turning into a web of arrows.

- **⌨️ Streaming Answers** — Responses arrive token by token as the local model generates them, so the first words appear in seconds instead of after a minute of blank screen.

- **🔑 Session-Based Accounts** — Register and sign in with a password (PBKDF2-SHA256, per-user salt). Every analysis and query endpoint requires a valid session token, which is verified server-side on each request.

- **📝 AI-Generated README Drafts** — Generates a concise, fact-grounded README summary of any indexed repository, with the same hallucination guard applied.

- **🔒 100% Local Inference** — Powered by Microsoft Foundry Local running `qwen2.5-coder-1.5b` on-device. No API keys, no cloud calls, no data leaves your machine.

---

## Architecture

```
                          GitHub Repo URL
                                │
    ┌───────────────────────────┼───────────────────────────┐
    ▼                           ▼                           ▼
┌────────────┐          ┌──────────────┐          ┌──────────────────┐
│  Fetcher   │─ files ─▶│  AST Parser  │─chunks─▶ │  SQLite Indexer  │
│ (REST API, │          │  (functions, │          │  chunks + raw    │
│  parallel) │          │   classes,   │          │  file contents   │
└────────────┘          │   methods,   │          │  + users/sessions│
                        │   imports)   │          └──────────────────┘
                        └──────────────┘                   │
                                                 ┌─────────┴─────────┐
                                                 ▼                   ▼
                                        ┌─────────────────┐  ┌──────────────┐
                                        │  TF-IDF Search  │  │   Diagram    │
                                        │  + vocabulary   │  │  Generator   │
                                        │    coverage     │  │ (import graph)│
                                        └─────────────────┘  └──────────────┘
                                                 │                   │
                                                 ▼                   │
                                        ┌─────────────────┐          │
                                        │  Foundry Local  │          │
                                        │  (grounded Q&A, │          │
                                        │   streamed)     │          │
                                        └─────────────────┘          │
                                                 │                   │
                          ┌──────────────────────┴───────────────────┘
                          ▼
                 ┌──────────────────────┐
                 │  FastAPI REST API    │
                 │  /analyze  /ask-stream│
                 │  /generate-readme     │
                 │  /login /register /me │
                 └──────────────────────┘
                          │
                          ▼
                 ┌──────────────────────┐
                 │  React + Tailwind    │
                 │  Dark IDE-style UI   │
                 └──────────────────────┘
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
| Diagram Generation | Mermaid.js (AST-based `import` extraction) |
| Auth | Session tokens in SQLite, PBKDF2-SHA256 password hashing |
| Frontend | React (Vite) + Tailwind CSS + lucide-react |

---

## Getting Started

### Prerequisites
- [Microsoft Foundry Local](https://learn.microsoft.com/en-us/azure/ai-foundry/foundry-local/) installed (the backend starts it for you)
- Python 3.10+
- Node.js 18+

### Backend

```bash
cd backend
python -m venv venv
venv\Scripts\activate        # Windows
pip install -r requirements.txt

uvicorn main:app --reload
```

On startup the backend checks Foundry Local, starts the daemon if it is not
running, and loads `qwen2.5-coder-1.5b` into memory — no manual setup needed.
The daemon picks a different port on each restart, so its address is resolved
from `foundry status` at call time rather than hardcoded.

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173`, create an account, paste a public GitHub repo URL
(e.g. `https://github.com/psf/requests`), and click **Analyze**.

Indexing takes a few seconds. The AI-written README is generated in the
background afterwards and takes a couple of minutes on a local model — the
diagram and file explorer are usable immediately.

---

## Design Decisions & Trade-offs

A few deliberate engineering calls worth noting:

- **TF-IDF over embeddings:** Chosen for speed and zero extra dependencies at this scale (hundreds of chunks). For much larger codebases, a proper embedding-based vector store would be the natural next step.
- **`qwen2.5-coder-1.5b` over the 7B variant:** The development machine's limited RAM made the 7B model unreliable for consistent local inference. The 1.5B model still produces accurate, grounded answers at a fraction of the latency — a hardware constraint that turned out to be an acceptable latency/quality trade-off for a real-time chat interface.
- **Single-repo indexing:** The current scope re-indexes on each new analysis rather than maintaining multiple repos simultaneously — a deliberate MVP boundary, not a limitation of the underlying architecture.
- **Vocabulary coverage as a guardrail:** TF-IDF silently discards query terms it has never seen, which meant an off-topic question could score *higher* than a real one by matching on whatever generic words survived. Scoring a question by how much of its distinctive vocabulary actually exists in the index closes that gap without a second model.
- **README off the critical path:** Generating it inline made indexing take ~175s, nearly all of it spent writing a document the user had not opened yet. It now runs in the background after the diagram is already on screen.

---

## Roadmap

- [ ] Multi-language support beyond Python (JS/TS, Go)
- [ ] Persistent multi-repo indexing
- [ ] Embedding-based retrieval for large-scale codebases
- [ ] Adjustable fast/deep inference mode (lightweight vs. larger local model)

---

## Author

Built by **Hayrunnisa Yorgun** as part of Microsoft's 2026 AI Summer Internship Program.
