import os
import re
import shutil
import threading
import time
import uuid
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel

from rag_pipeline import ingest_contract
from compliance_rules import run_compliance_check, format_checklist_markdown, DEFAULT_RULES
from agent import build_agent_executor, run_initial_analysis, run_follow_up

# ── Configuration ──────────────────────────────────────────────────────────
OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL    = os.environ.get("OLLAMA_MODEL", "qwen3:0.6b")
EMBEDDING_MODEL = os.environ.get("EMBEDDING_MODEL", "nomic-embed-text")

BASE_DIR = Path(__file__).resolve().parent
TEMP_DIR = BASE_DIR / "temp"
TEMP_DIR.mkdir(exist_ok=True)
STATIC_DIR = BASE_DIR / "static"

app = FastAPI(title="Legal Vision", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
)


class _NoStoreMiddleware(BaseHTTPMiddleware):
    """Never let the browser cache the page or its assets, so frontend
    fixes always show up without a hard refresh."""

    async def dispatch(self, request, call_next):
        response = await call_next(request)
        if request.url.path == "/" or request.url.path.startswith("/static/"):
            response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"
        return response


app.add_middleware(_NoStoreMiddleware)

# ── Module-level single-session state (one ingested contract) ──────────────
SESSION_LOCK = threading.Lock()
SESSION = {
    "agent": None,
    "messages": [],
    "contract_text": "",
    "ready": False,
}

# ── Job store ──────────────────────────────────────────────────────────────
JOBS_LOCK = threading.Lock()
JOBS: dict[str, dict] = {}
JOB_DEADLINES = {
    "upload": 900,   # 15 min
    "ask":    420,   # 7 min
}

DEADLINE_ERROR = (
    "Analysis timed out — the engine stopped responding mid-analysis. "
    "Please re-upload the contract. If this keeps happening, restart with start.bat."
)


def _now() -> float:
    return time.time()


def start_job(kind: str, **payload) -> str:
    job_id = uuid.uuid4().hex[:12]
    with JOBS_LOCK:
        JOBS[job_id] = {
            "id": job_id, "kind": kind, "status": "pending",
            "stage": "Queued", "progress": 0.0,
            "result": None, "error": None, "created": _now(),
        }
    thread = threading.Thread(
        target=_run_job, args=(job_id, kind), kwargs=payload, daemon=True
    )
    thread.start()
    return job_id


def _update_job(job_id: str, **fields) -> None:
    with JOBS_LOCK:
        if job_id in JOBS:
            JOBS[job_id].update(fields)


def _run_job(job_id: str, kind: str, **payload) -> None:
    _update_job(job_id, status="running")
    try:
        if kind == "upload":
            result = _do_upload(payload["path"])
        elif kind == "ask":
            result = _do_ask(payload["question"])
        else:
            raise ValueError(f"Unknown job kind: {kind}")
        _update_job(job_id, status="done", result=result, progress=1.0)
    except Exception as exc:  # noqa: BLE001
        _update_job(job_id, status="error", error=str(exc))


# ── Job bodies ─────────────────────────────────────────────────────────────
def _safe_name(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", Path(name).name) or "contract"


def _ingest_with_heal(path: str) -> dict:
    """Ingest a contract, auto-rebuilding a corrupt vector store once.

    A previously interrupted analysis (e.g. the engine was killed mid-write)
    can leave the persistent Chroma DB truncated. Chroma then fails with
    SQLite errors like 'no such table: tenants'. The store is disposable
    (rebuilt on every upload), so on failure we wipe it and retry once."""
    try:
        return ingest_contract(
            path,
            collection_name="contract_rag",
            embedding_model=EMBEDDING_MODEL,
            base_url=OLLAMA_BASE_URL,
        )
    except Exception as exc:  # noqa: BLE001
        _update_job_progress("Vector store unhealthy — rebuilding", 0.3)
        shutil.rmtree(BASE_DIR / "chroma_store", ignore_errors=True)
        return ingest_contract(
            path,
            collection_name="contract_rag",
            embedding_model=EMBEDDING_MODEL,
            base_url=OLLAMA_BASE_URL,
        )


def _build_redline(clauses: list[str], results: list) -> dict:
    """Map compliance results back onto individual clauses so the frontend can
    render a 'living document' redline: every clause knows which protections it
    contains, and how important they are (severity = clause heat)."""
    normalized = [re.sub(r"\s+", " ", c).lower() for c in clauses]

    clause_rules: dict[int, list[dict]] = {}
    for r in results:
        if r.status != "pass":
            continue
        rule = r.rule
        snippet = (r.matched_text or "").strip()
        snip = re.sub(r"\s+", " ", snippet).lower()
        hit_idx = None

        # 1) exact snippet match against a clause
        if len(snip) >= 15:
            for ci, cn in enumerate(normalized):
                if snip in cn:
                    hit_idx = ci
                    break
        # 2) fallback: any rule keyword present in the clause
        if hit_idx is None:
            kws = [k.lower() for k in rule.keywords]
            for ci, cn in enumerate(normalized):
                if any(kw in cn for kw in kws):
                    hit_idx = ci
                    break
        if hit_idx is not None:
            clause_rules.setdefault(hit_idx, []).append({
                "name": rule.name,
                "severity": rule.severity,
                "category": rule.category,
                "matched": snip[:100] or "",
            })

    def _head(text: str, limit: int = 90) -> str:
        first = next((ln.strip() for ln in text.splitlines() if ln.strip()), "")
        return (first[:limit] + "…") if len(first) > limit else first or "Clause"

    clauses_out = []
    hot = {"high": 0, "medium": 0, "low": 0}
    for i, c in enumerate(clauses):
        rules = clause_rules.get(i, [])
        sev = max((r["severity"] for r in rules), default=None)
        if sev:
            hot[sev] += 1
        clauses_out.append({
            "idx": i,
            "head": _head(c),
            "text": c,
            "rules": rules,
            "heat": sev or "none",
        })

    return {
        "clauses": clauses_out,
        "hot": hot,
        "missing_count": sum(1 for r in results if r.status == "missing"),
    }


def _do_upload(path: str) -> dict:
    _update_job_progress("Loading document and splitting into clauses", 0.05)
    ingest_result = _ingest_with_heal(path)
    chunks = [c.page_content for c in ingest_result["chunks"]]

    # Raw text
    from langchain_community.document_loaders import PyPDFLoader, TextLoader
    ext = Path(path).suffix.lower()
    if ext == ".pdf":
        pages = PyPDFLoader(path).load()
        raw = "\n\n".join(p.page_content for p in pages)
    else:
        docs = TextLoader(path, encoding="utf-8").load()
        raw = "\n\n".join(d.page_content for d in docs)

    # Deterministic compliance checklist (structured, for cards)
    _update_job_progress("Running deterministic compliance checklist", 0.35)
    results = run_compliance_check(raw, DEFAULT_RULES)
    checklist = {
        "total": len(results),
        "passed": sum(1 for r in results if r.status == "pass"),
        "missing": sum(1 for r in results if r.status == "missing"),
        "results": [
            {
                "name": r.rule.name,
                "category": r.rule.category,
                "severity": r.rule.severity,
                "status": r.status,
                "description": r.rule.description,
                "keywords": r.rule.keywords,
                "explanation": r.explanation,
                "matched_text": r.matched_text,
            }
            for r in results
        ],
        "missing_names": [r.rule.name for r in results if r.status == "missing"],
    }
    checklist_md = format_checklist_markdown(results)

    # Agent: single LLM plain-English summary (the checklist above is already
    # complete — only one short LLM pass is needed, no per-clause repeats)
    _update_job_progress("Generating plain-language summary (one LLM pass)", 0.5)
    with SESSION_LOCK:
        SESSION["contract_text"] = raw
        SESSION["checklist_md"] = checklist_md
        SESSION["messages"] = []
        SESSION["agent"] = build_agent_executor()
        _update_job_progress("Generating plain-language summary", 0.7)
        report, SESSION["messages"] = run_initial_analysis(
            SESSION["agent"],
            raw,
            SESSION["messages"],
            precomputed_checklist_md=checklist_md,
        )
        SESSION["ready"] = True

    return {
        "chunk_count": len(chunks),
        "checklist": checklist,
        "report": report,
        "summary": _extract_summary(report),
        "redline": _build_redline(chunks, results),
    }


def _extract_summary(report: str) -> str:
    """Return the human-facing part of the report (skip the checklist dupe)."""
    for marker in ("## Agent's Plain-Language Summary", "## Plain-English Clause Summary"):
        idx = report.find(marker)
        if idx != -1:
            return report[idx:]
    return report


def _do_ask(question: str) -> dict:
    with SESSION_LOCK:
        if not SESSION["ready"] or SESSION["agent"] is None:
            raise HTTPException(
                status_code=400,
                detail="No contract analyzed yet. Upload a contract first.",
            )
        _update_job_progress("Gathering all clauses relevant to the question", 0.3)
        answer, citation, SESSION["messages"] = run_follow_up(
            SESSION["agent"], question, SESSION["messages"],
            compliance_md=SESSION.get("checklist_md"),
            progress=lambda stage, frac: _update_job_progress(stage, frac),
        )
    return {"question": question, "answer": answer, "citation": citation}


def _update_job_progress(stage: str, progress: float):
    current = JOBS.copy()
    for job in current.values():
        if job["status"] == "running":
            _update_job(job["id"], stage=stage, progress=progress)


# ── HTTP API ───────────────────────────────────────────────────────────────
class AskBody(BaseModel):
    question: str


@app.get("/api/health")
async def health():
    try:
        import httpx
        r = httpx.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=3)
        ok = r.status_code == 200
        models = [m["name"] for m in r.json().get("models", [])] if ok else []
        return {
            "status": "ok" if ok else "degraded",
            "ollama": ok,
            "base_url": OLLAMA_BASE_URL,
            "model": OLLAMA_MODEL,
            "embedding_model": EMBEDDING_MODEL,
            "models": models,
        }
    except Exception as exc:  # noqa: BLE001
        return {"status": "error", "ollama": False, "detail": str(exc)}


@app.post("/api/upload")
async def upload_contract(file: UploadFile = File(...)):
    name = _safe_name(file.filename or "contract")
    dest = TEMP_DIR / f"{int(time.time())}_{name}"
    content = await file.read()
    dest.write_bytes(content)
    job_id = start_job("upload", path=str(dest))
    return {"job_id": job_id}


@app.post("/api/ask")
async def ask_question(body: AskBody):
    question = (body.question or "").strip()
    if not question:
        raise HTTPException(status_code=400, detail="Question cannot be empty.")
    job_id = start_job("ask", question=question)
    return {"job_id": job_id}


@app.get("/api/jobs/{job_id}")
def get_job(job_id: str):
    with JOBS_LOCK:
        job = JOBS.get(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="Job not found.")
        # A worker thread stuck inside a hung LLM call never sets a terminal
        # state — enforce a wall-clock deadline so the UI gets a clear error.
        if job.get("status") in ("pending", "running"):
            limit = JOB_DEADLINES.get(job.get("kind"), 900)
            if _now() - job.get("created", 0) > limit:
                job["status"] = "error"
                job["error"] = DEADLINE_ERROR
                job["progress"] = 1.0
        return dict(job)


# ── Static frontend ────────────────────────────────────────────────────────
@app.get("/")
def index():
    # Tag the page so the frontend KNOWS it is hosted by the engine.
    # Pages served elsewhere (VS Code preview, file://) don't get the tag and
    # the JS talks straight to the backend without probing foreign hosts.
    html = (STATIC_DIR / "index.html").read_text(encoding="utf-8")
    html = html.replace(
        "</head>",
        '    <script>window.__LEGAL_VISION_BACKEND__ = true;</script>\n  </head>',
        1,
    )
    return HTMLResponse(html)


app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


if __name__ == "__main__":
    import sys

    try:
        import uvicorn  # noqa: F401
    except ImportError:
        print("\n*** ERROR: Python dependencies are missing ***")
        print("Run from the project folder:")
        print("    .venv\\Scripts\\python.exe -m pip install -r requirements.txt")
        sys.exit(1)

    port = int(os.environ.get("WEB_PORT", "8000"))

    import socket

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as _s:
        _s.settimeout(1)
        _in_use = _s.connect_ex(("127.0.0.1", port)) == 0
    if _in_use:
        print(f"\n*** ERROR: Port {port} is already in use ***")
        print("Another Legal Vision backend may already be running.")
        print("Stop it first, or use start.bat (it cleans up stale instances).")
        sys.exit(1)

    print(f"Legal Vision frontend -> http://localhost:{port}")
    uvicorn.run("backend:app", host="0.0.0.0", port=port, reload=False)