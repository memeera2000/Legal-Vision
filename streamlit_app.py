import os
import shutil
import sys
import tempfile
import socket
import subprocess
from pathlib import Path

import streamlit as st


def _backend_port_open(port: int = 8000) -> bool:
    """True if the web backend (backend.py) is already listening on the port."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex(("127.0.0.1", port)) == 0


def _ensure_backend_running() -> None:
    """Auto-start backend.py if it isn't already running, so the web frontend
    is available at http://localhost:8000 whenever this app is launched."""
    if _backend_port_open():
        return
    root = Path(__file__).resolve().parent
    py = root / ".venv" / "Scripts" / "python.exe"
    interpreter = str(py) if py.exists() else sys.executable
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0
    try:
        subprocess.Popen(
            [interpreter, str(root / "backend.py")],
            cwd=str(root),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=flags,
            close_fds=True,
        )
    except Exception:
        pass  # best-effort; the page itself retries via the health badge

try:
    import streamlit.runtime as _st_runtime
    _RUNNING_UNDER_STREAMLIT = _st_runtime.exists()
except Exception:
    _RUNNING_UNDER_STREAMLIT = False

if not _RUNNING_UNDER_STREAMLIT:
    st.error(
        "Streamlit must be launched with `streamlit run`, not `python`.\n\n"
        "Run this instead:\n\n"
        "    streamlit run streamlit_app.py\n\n"
        "or double-click **start-streamlit.bat**"
    )
    st.stop()

# Keep the web frontend (backend.py on :8000) running automatically.
_ensure_backend_running()

st.set_page_config(
    page_title="Legal Vision — Contract Simplifier & Compliance Agent",
    page_icon="⚖️",
    layout="wide",
    initial_sidebar_state="expanded",
)

from rag_pipeline import ingest_contract
from agent import build_agent_executor, run_initial_analysis, run_follow_up
from compliance_rules import run_compliance_check, format_checklist_markdown, DEFAULT_RULES

# ── Configuration ──────────────────────────────────────────────────────────
OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL    = os.environ.get("OLLAMA_MODEL", "qwen3:1.7b")
EMBEDDING_MODEL = os.environ.get("EMBEDDING_MODEL", "nomic-embed-text")

DISCLAIMER = (
    "⚠️ **DISCLAIMER**: This tool is for informational and educational purposes only. "
    "The analysis provided is **NOT a substitute for a licensed attorney's review**. "
    "Always consult a qualified legal professional before making legal decisions."
)

# ── Session state ──────────────────────────────────────────────────────────
if "agent_executor" not in st.session_state:
    st.session_state.agent_executor = None
if "messages" not in st.session_state:
    st.session_state.messages = []
if "analyzed" not in st.session_state:
    st.session_state.analyzed = False


def do_ingest(file_path: str):
    """Ingest contract into RAG (clause-aware split -> Chroma) and run the agent."""
    ingest_result = ingest_contract(
        file_path,
        collection_name="contract_rag",
        embedding_model=EMBEDDING_MODEL,
        base_url=OLLAMA_BASE_URL,
    )
    st.session_state.ingest_result = ingest_result

    # Raw text
    from langchain_community.document_loaders import PyPDFLoader, TextLoader
    ext = Path(file_path).suffix.lower()
    if ext == ".pdf":
        pages = PyPDFLoader(file_path).load()
        raw = "\n\n".join(p.page_content for p in pages)
    else:
        docs = TextLoader(file_path, encoding="utf-8").load()
        raw = "\n\n".join(d.page_content for d in docs)
    st.session_state.contract_text = raw


# ── Header ─────────────────────────────────────────────────────────────────
st.title("⚖️ Legal Vision")
st.subheader("Contract Simplifier & Compliance Agent")
st.markdown(DISCLAIMER)
st.divider()

# ── Sidebar: upload & status ───────────────────────────────────────────────
with st.sidebar:
    st.header("📄 Upload Contract")
    uploaded = st.file_uploader(
        "Upload your contract or policy (PDF, TXT, MD)",
        type=["pdf", "txt", "md"],
        key="contract_upload",
    )
    run_btn = st.button("🔍 Analyze Contract", type="primary", use_container_width=True, key="analyze_btn")

    if st.session_state.analyzed:
        st.success("✅ Contract ingested & checklist run")
        with st.expander("RAG pipeline info"):
            chunks = st.session_state.ingest_result["chunks"]
            st.write(f"**Clause chunks embedded:** {len(chunks)}")
            for i, c in enumerate(chunks[:20]):
                st.caption(f"• Chunk {i}: {c.page_content[:60].strip()}")

if run_btn:
    if uploaded is None:
        st.error("Please upload a file first.")
    else:
        with st.spinner("Ingesting contract into RAG + running compliance analysis…"):
            # Save to temp
            tmp_path = Path("temp") / Path(uploaded.name).name
            tmp_path.parent.mkdir(exist_ok=True)
            tmp_path.write_bytes(uploaded.getvalue())

            do_ingest(str(tmp_path))

            # Reset messages, build agent, auto-run simplify_and_check
            st.session_state.messages = []
            st.session_state.agent_executor = build_agent_executor()
            st.session_state.analyzed = True
            st.rerun()

# ── Main panel ─────────────────────────────────────────────────────────────
if not st.session_state.analyzed:
    st.info(
        "Upload your contract on the left and click **Analyze Contract**. "
        "Before you ask anything, the agent will:\n\n"
        "1. Rewrite dense clauses into **plain English**\n"
        "2. Run a **compliance checklist** — flagging what's present and what's missing (deterministic regex/keyword checks)\n"
        "3. Only then accept your questions, each answered with **exact clause citations**.",
    )
else:
    # ── 1) Deterministic compliance checklist (always shown immediately) ────
    st.header("✅ Compliance Checklist")
    with st.spinner("Running deterministic compliance checks…"):
        results = run_compliance_check(st.session_state.contract_text, DEFAULT_RULES)
        checklist_md = format_checklist_markdown(results)
    with st.expander("View compliance checklist", expanded=True):
        st.markdown(checklist_md)

    # ── 2) Agent auto-run report (plain-English simplification etc.) ────────
    st.header("🗣️ Agent Report (auto-generated on upload)")
    if "agent_report" not in st.session_state:
        with st.spinner("LLM is simplifying clauses…"):
            try:
                st.session_state.agent_report, st.session_state.messages = run_initial_analysis(
                    st.session_state.agent_executor,
                    st.session_state.contract_text,
                    st.session_state.messages,
                )
            except Exception as e:
                st.session_state.agent_report = f"[LLM analysis unavailable: {e}]"
                st.warning("The LLM is running; deterministic checklist above is still valid.")
    with st.expander("Agent report", expanded=True):
        st.markdown(st.session_state.agent_report)

    st.divider()

    # ── 3) Follow-up Q&A with clause citations ──────────────────────────────
    st.header("💬 Ask a follow-up question")
    st.caption("Answers cite the exact retrieved clause text they are based on.")
    question = st.text_input("e.g. What is the termination notice period?", key="question_box")

    if st.button("Ask", type="secondary", key="ask_btn"):
        if question.strip():
            with st.spinner("Retrieving the relevant clause and answering…"):
                try:
                    answer, citation, st.session_state.messages = run_follow_up(
                        st.session_state.agent_executor,
                        question.strip(),
                        st.session_state.messages,
                    )
                except Exception as e:
                    answer, citation = f"❌ Error: {e}", ""
            # stash answer + citation for display below after fresh render
            st.session_state.last_answer = answer
            st.session_state.last_citation = citation
            st.rerun()

    last_answer = st.session_state.get("last_answer")
    if last_answer:
        st.markdown(last_answer)
    last_citation = st.session_state.get("last_citation")
    if last_citation:
        st.divider()
        st.markdown(last_citation)

st.markdown("---")
st.markdown("Build with LangChain RAG + ChatOllama + Chroma. Not legal advice.")