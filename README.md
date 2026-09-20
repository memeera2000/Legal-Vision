# Legal Vision

AI contract review for lawyers — upload a contract (PDF/DOCX/TXT), get a
clause-level RISK analysis, a severity score, redline suggestions and a
plain-language summary, then chat with the document.

## Features

- Drag-and-drop first screen (compact, centered upload card)
- Live animated law-themed background (gold contract pages + sparks,
  theme-aware: switches palette with light/dark)
- Clause-level risk flags + overall severity ring
- Redline suggestions, checklist and a markdown summary
- RAG chat over your document (Chroma vector store + Ollama embeddings)

## Requirements

- Windows
- Python 3.14 (project ships its own `.venv`)
- Ollama running on `http://localhost:11434` with a pull of your
  `embedding_model` (default `nomic-embed-text`) for RAG ingestion

## Run

```powershell
# from the project folder
.\.venv\Scripts\python.exe backend.py
```

Then open the printed address (default `http://localhost:8000`). Use
Ctrl+F5 if the page looks stale (assets are cache-busted with `?v=`).

## Upload flow

1. Drop a contract PDF / DOCX / TXT / image onto the center card.
2. Wait for the ingest + analysis round (calls the local Ollama model).
3. The sidebar shows the full panel set; ask the AI questions in chat.

## Project layout

```
Legal Vision/
  backend.py          FastAPI app: serves /static and /api, owns lifecycle
  rag_pipeline.py     Chroma vector store build/load/retriever + recovery
  compliance_rules.py risk rule engine
  agent.py            LLM agent + tool dispatch
  legal_reference.py  legal citation helpers + RAG retrieval UX
  tools.py            small shared utilities
  static/             frontend (index.html, app.js, style.css)
  temp/               upload staging + server logs
  chroma_store/       Chroma persistence (SQLite) — disposable
```

## Getting "no such table: tenants"?

That is a **corrupt Chroma SQLite store** (a killed/interrupted engine
write leaves `chroma_store\chroma.sqlite3` at 0 bytes). Fix:

1. Stop any running `backend.py` process.
2. Delete the whole `chroma_store\` directory.
3. Restart `backend.py` and re-upload the contract once.

The pipeline also self-heals: an empty/corrupt store is detected, wiped
and rebuilt automatically instead of surfacing the SQL error.

## Notes

- `chroma_store/` is a scratch store — delete it freely; it rebuilds on
  the next upload with no data loss beyond a re-ingest.
- The 3D gold scales-of-justice modules live in `static/scales/`
  (`math.mjs`, `build.mjs`, `scene.mjs`) — authored and syntax-verified,
  not yet wired into the served page.