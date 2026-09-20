import os
import re
from typing import Optional, Type

from langchain.tools import BaseTool, tool
from langchain_core.language_models.chat_models import BaseChatModel
from pydantic import BaseModel, Field

from compliance_rules import (
    run_compliance_check,
    format_checklist_markdown,
    DEFAULT_RULES,
)


# ---------------------------------------------------------------------------
# Tool 1: Clause simplification & compliance checklist (auto-runs on ingest)
# ---------------------------------------------------------------------------
class ChecklistInput(BaseModel):
    contract_text: str = Field(description="The full text of the contract to analyze.")
    llm_summary: bool = Field(
        default=True,
        description="Whether to also generate plain-English simplifications using the LLM (True) or only deterministic checks (False).",
    )


@tool("simplify_and_check", args_schema=ChecklistInput)
def simplify_and_check(contract_text: str, llm_summary: bool = True) -> str:
    """Contract Clause Simplifier & Compliance Checklist tool.

    Automatically runs the moment a contract is ingested. Performs two jobs:
      1) CLause simplification: rewrites dense legal clauses into plain English
         using the LLM when llm_summary=True.
      2) Compliance checklist: deterministically checks the contract text
         (regex + keyword matching) against a fixed set of compliance rules
         (parties identification, term, termination, confidentiality, IP,
         limitation of liability, indemnification, governing law, dispute
         resolution, force majeure, payment terms, data protection, warranties,
         assignment, entire agreement, severability).

    Returns a Markdown report:
      - a pass/fail/missing verdict per required clause type,
      - the plain-English simplification summary,
      - and the list of what is present vs missing.
    """
    # Deterministic compliance check (always runs)
    results = run_compliance_check(contract_text, DEFAULT_RULES)
    checklist_md = format_checklist_markdown(results)

    # Optional LLM plain-English simplification
    simplification = ""
    if llm_summary:
        from langchain_ollama import ChatOllama

        llm = ChatOllama(
            model=os.environ.get("OLLAMA_MODEL", "qwen3:0.6b"),
            base_url=os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434"),
            temperature=1.0,
            keep_alive="1h",
            num_ctx=8192,
            num_predict=900,
            num_thread=int(os.environ.get("OLLAMA_NUM_THREAD", max(2, os.cpu_count() or 4))),
        )
        try:
            from compliance_rules import simplify_clauses_with_llm
            simplification = simplify_clauses_with_llm(contract_text, llm)
        except Exception as e:
            simplification = f"[LLM simplification unavailable: {e}]"

    report = []
    report.append("# Contract Analysis Report\n")
    report.append(checklist_md)
    report.append("\n\n---\n")
    if simplification:
        report.append("## Plain-English Clause Summary\n")
        report.append(simplification)

    return "\n".join(report)


# ---------------------------------------------------------------------------
# Tool 2: Retrieve contract text (RAG-backed, returns exact clause for citation)
# ---------------------------------------------------------------------------
class RetrieveInput(BaseModel):
    query: str = Field(description="The question or topic to find the relevant clause for.")
    k: int = Field(default=3, ge=1, le=10, description="Number of clause chunks to retrieve.")


_STOPWORDS = frozenset({
    "what", "which", "when", "where", "who", "whose", "how", "does", "do",
    "did", "can", "could", "would", "should", "will", "shall", "must", "may",
    "and", "or", "for", "not", "with", "from", "this", "that", "these",
    "those", "you", "your", "our", "their", "it", "its", "is", "are", "was",
    "were", "have", "has", "had", "about", "into", "also", "tell", "give",
    "find", "show", "contract",
})


def _query_terms(query: str) -> list[str]:
    """Extract the meaningful search terms from a question."""
    toks = re.findall(r"[A-Za-z][A-Za-z0-9_]*", query.lower())
    return [t for t in toks if len(t) >= 4 and t not in _STOPWORDS]


def _hit_count(text: str, terms: list[str]) -> int:
    """How many of the question's key terms appear in a chunk."""
    low = text.lower()
    return sum(1 for t in terms if t in low)


def _get_vectorstore():
    from rag_pipeline import load_vectorstore

    return load_vectorstore()


@tool("retrieve_contract_text", args_schema=RetrieveInput)
def retrieve_contract_text(query: str, k: int = 3) -> str:
    """Retrieve the contract clauses that answer a question — hybrid search.

    RAG tool: embeds the query and searches the persisted Chroma vector store
    for semantically related clauses, then augments the results with any OTHER
    clauses that mention the question's key words, so the answer is grounded in
    ALL relevant language in the document, not just the single closest chunk.
    Returns the verbatim contract text with clause references.
    """
    vs = _get_vectorstore()
    all_docs = vs.similarity_search(query, k=100000)  # every chunk
    if not all_docs:
        return "No matching clause found in the ingested contract."

    terms = _query_terms(query)
    k = max(2, min(k, 10))

    # 1) Top semantic matches first (highest cosine similarity).
    picked, seen = [], set()
    sem_keep = max(2, k // 2)
    for d in all_docs[:sem_keep]:
        if d.page_content not in seen:
            seen.add(d.page_content)
            picked.append(d)

    # 2) Then any clause mentioning the most query terms (keyword coverage),
    #    even if the vector search ranked it lower.
    if terms and len(picked) < k:
        scored = sorted(
            (d for d in all_docs if d.page_content not in seen),
            key=lambda d: (-_hit_count(d.page_content, terms), d.metadata.get("chunk_index", 0)),
        )
        for d in scored:
            if len(picked) >= k:
                break
            if _hit_count(d.page_content, terms) > 0:
                seen.add(d.page_content)
                picked.append(d)

    out = []
    for i, d in enumerate(picked, 1):
        idx = d.metadata.get("chunk_index", "?")
        out.append(f"--- Retrieved chunk {i} of {len(picked)} (document clause number {idx}) ---")
        out.append(d.page_content.strip())
        out.append("")
    return "\n".join(out).strip() or "No matching clause found in the ingested contract."


# ---------------------------------------------------------------------------
# Tool bindings used by the agent
# ---------------------------------------------------------------------------
def build_tools(llm: Optional[BaseChatModel] = None) -> list[BaseTool]:
    return [simplify_and_check, retrieve_contract_text]