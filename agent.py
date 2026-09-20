import os
from typing import Callable, Optional

import httpx
from langchain.agents import create_agent
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import HumanMessage, AIMessage
from langchain_ollama import ChatOllama

from tools import build_tools, simplify_and_check, retrieve_contract_text
from legal_reference import law_references_for


SYSTEM_PROMPT = """\
You are Legal Vision, a contract analysis assistant that helps non-lawyers
understand their contracts and the Indian law that applies to them.

BEHAVIOUR:
- On upload, the simplify_and_check tool has ALREADY been run automatically and
  its report is provided to you. Present it as a clear, friendly, plain-English
  summary: what the contract covers and which clauses are present or missing.
  Do not invent results that are not in the report.
- For follow-up questions, the exact clause has ALREADY been retrieved with the
  retrieve_contract_text tool and its verbatim text will be given to you.
  Answer the question in plain English and CITE the exact clause text you based
  your answer on. If the retrieved text does not answer the question, say so.
- When the question asks about the LAW behind the document, use ONLY the exact
  Indian statute sections provided in the LEGAL REFERENCES block (IPC/BNS and
  substantive acts). Never invent or guess a section number. Give both numbers
  when applicable (e.g. IPC s.420 / BNS s.318(4)) and separate civil remedies
  from criminal remedies (FIR / police complaint).
- Answer directly and concisely: plain, clear English — never legalese. Keep
  answers tight (bullets), but include the specific numbers, periods and
  amounts that matter.
- The app page ALREADY displays the notice "informational and educational
  purposes only". Never repeat or add a legal disclaimer yourself — answer the
  question directly. A bare disclaimer or a one-line caution is NEVER a valid
  answer: always give the substantive answer to the user's question.
- If the provided text lacks the answer, say so and explain what would be needed.
"""


def build_llm(
    base_url: str = "http://localhost:11434",
    model: str = "qwen3:0.6b",
    num_predict: int = 900,
    temperature: float = 1.0,
    num_ctx: int = 8192,
):
    base_url = os.environ.get("OLLAMA_BASE_URL", base_url)
    model = os.environ.get("OLLAMA_MODEL", model)
    threads = int(os.environ.get("OLLAMA_NUM_THREAD", max(2, os.cpu_count() or 4)))
    return ChatOllama(
        model=model,
        base_url=base_url,
        temperature=temperature,
        keep_alive="2h",
        num_predict=num_predict,
        num_ctx=num_ctx,
        num_thread=threads,
    )


def _charges() -> tuple[str, str, int]:
    """Resolved Ollama endpoint, model and thread count from the environment."""
    base = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
    model = os.environ.get("OLLAMA_MODEL", "qwen3:0.6b")
    threads = int(os.environ.get("OLLAMA_NUM_THREAD", max(2, os.cpu_count() or 4)))
    return base, model, threads


def _as_chat_messages(history) -> list[dict]:
    """Convert our history (langchain messages OR plain role/content dicts)
    into Ollama chat-API message dicts."""
    out = []
    for m in history:
        role = c = None
        if isinstance(m, dict):
            role, c = m.get("role"), m.get("content")
        else:
            role = "user" if isinstance(m, HumanMessage) else "assistant"
            c = getattr(m, "content", "")
        if isinstance(c, list):
            c = "".join(str(p.get("text", "")) for p in c if isinstance(p, dict))
        if role and c:
            out.append({"role": role, "content": str(c)})
    return out


def _chat(messages, system: Optional[str] = None, num_predict: int = 700,
          temperature: float = 0.4, timeout: int = 600) -> str:
    """Single non-thinking Ollama completion (fast on CPU): returns the text."""
    base, model, threads = _charges()
    chat = []
    if system:
        chat.append({"role": "system", "content": system})
    chat.extend(_as_chat_messages(messages))
    body = {
        "model": model,
        "messages": chat,
        "stream": False,
        "think": False,          # qwen3 writes hidden "thinking" tokens otherwise
        "keep_alive": "2h",
        "options": {
            "num_predict": num_predict,
            "temperature": temperature,
            "num_thread": threads,
            "num_ctx": 8192,
        },
    }
    r = httpx.post(f"{base}/api/chat", json=body, timeout=timeout)
    r.raise_for_status()
    return r.json()["message"]["content"] or ""


def build_agent_executor(llm: Optional[BaseChatModel] = None):
    """Build the tool-calling agent. Both @tool functions are bound so the
    agent remains available to other entry points."""
    if llm is None:
        llm = build_llm()
    tools = build_tools(llm)
    agent = create_agent(
        model=llm,
        tools=tools,
        system_prompt=SYSTEM_PROMPT,
        name="legal_vision",
    )
    return agent


# ---------------------------------------------------------------------------
# Guaranteed auto-run on ingestion
# ---------------------------------------------------------------------------
def run_initial_analysis(
    agent,
    contract_text: str,
    messages: list,
    precomputed_checklist_md: Optional[str] = None,
) -> tuple[str, list]:
    """Produces the report: deterministic checklist + a single fast LLM summary
    (one direct, non-thinking completion). Returns (combined_report, messages)."""

    if precomputed_checklist_md:
        report_so_far = (
            "# Contract Analysis Report\n\n"
            + precomputed_checklist_md
            + "\n\n---\n"
        )
    else:
        report_so_far = simplify_and_check.invoke(
            {"contract_text": contract_text, "llm_summary": True}
        )

    prompt = (
        "A contract has just been ingested. "
        "The simplify_and_check tool already ran automatically and produced the "
        "report below. Present it to the user as a concise plain-language summary: "
        "what the contract covers, what is present, and what is missing.\n"
        "Do NOT call any tools — the analysis is already complete.\n"
        "Do NOT add any legal disclaimer or warning — the page already shows one. "
        "Give the substantive summary.\n"
        "Keep the summary to at most ~180 words, tight bullets.\n\n"
        "=== simplify_and_check REPORT ===\n"
        f"{report_so_far}\n=== END ==="
    )
    final = _chat([{"role": "user", "content": prompt}],
                  system=SYSTEM_PROMPT, num_predict=650, temperature=0.6)
    if not final.strip():
        try:
            final = _chat([HumanMessage(
                "Give a concise 3-4 sentence plain-English overview of this "
                "compliance report for a non-lawyer:\n\n" + report_so_far[:3500]
            )], num_predict=500, temperature=0.4)
        except Exception:
            final = (
                "The automated checklist and plain-English clause summary above "
                "are complete. Ask me any follow-up question for a cited answer."
            )
    combined = (
        report_so_far
        + "\n\n---\n\n## Agent's Plain-Language Summary\n\n"
        + final
    )
    return combined, [{"role": "user", "content": prompt},
                      {"role": "assistant", "content": final}]


# ---------------------------------------------------------------------------
# Follow-up Q&A with guaranteed clause citation + Indian-law references
# ---------------------------------------------------------------------------
def run_follow_up(
    agent,
    question: str,
    messages: list,
    compliance_md: Optional[str] = None,
    answer_tokens: int = 300,
    progress: Optional[Callable[[str, float], None]] = None,
) -> tuple[str, str, list]:
    """Answers a follow-up question with maximum detail and citation.

    retrieve_contract_text is invoked directly with a widened k so the answer
    is grounded in EVERY clause that touches the topic (semantic + keyword
    coverage). A single direct completion (non-thinking, fast) is used with
    tight token/history budgets so each answer is quick; `progress(stage,
    fraction)` is invoked at each step so the UI can live-update. When the
    question is about the law behind the document, India-specific references
    (IPC/BNS and statute sections) are attached deterministically for accurate
    citation. Returns (answer, citation, updated_messages)."""
    def step(stage, frac):
        if progress:
            progress(stage, frac)

    step("Gathering all clauses relevant to the question", 0.3)
    clause_text = retrieve_contract_text.invoke({"query": question, "k": 4})
    clause_text = clause_text[:2600]
    step("Reading the clauses and the law that applies to them", 0.5)
    history = messages[-2:]

    snapshot = ""
    if compliance_md:
        snapshot = (
            "\nCompliance snapshot of the whole document (which protections are "
            "present vs missing) — reference it only if it is relevant to the "
            "question:\n" + compliance_md[:1600]
            + "\n--- END SNAPSHOT ---\n"
        )

    legal_md = law_references_for(question, clause_text)
    legal_block = ""
    if legal_md:
        legal_block = (
            "\n=== LEGAL REFERENCES (VALID FOR INDIA) ===\n"
            f"{legal_md}\n"
            "=== END LEGAL REFERENCES ===\n"
            "STATUTORY CITATION RULES:\n"
            "- Start your answer with 'Under Indian law, ...' naming the one or "
            "two most relevant sections from LEGAL REFERENCES.\n"
            "- Cite any section with its exact number (e.g. IPC s.420 / BNS s.318(4)). "
            "Never invent or guess a section number.\n"
            "- Separate civil remedies (sue for damages / specific performance) from "
            "criminal remedies (police complaint / FIR).\n"
            "- If pushed for length, PRIORITISE section numbers and clause numbers "
            "over re-quoting contract text.\n"
            "- Keep the whole answer tight — bullets, at most ~130 words."
        )

    prompt = (
        "The user asks: {question}\n\n"
        "The relevant clause text has ALREADY been retrieved from the contract "
        "(verbatim, below), and a compliance snapshot of the whole document is "
        "also provided for reference.\n\n"
        "Answer THOROUGHLY and ACCURATELY in plain English:\n"
        "- Open by directly answering the question.\n"
        "- Cover EVERY retrieved clause that touches the topic: state exactly "
        "what it provides, including the specific details — time periods, "
        "amounts, notice requirements, conditions, exceptions, and the parties "
        "covered. Do not omit these.\n"
        "- QUOTE the exact clause language you rely on. Each retrieved chunk is "
        "marked '--- Retrieved chunk X of Y (document clause number N) ---'; "
        "the number N is the real clause number in the contract and is the ONLY "
        "one to cite. Never invent or guess clause numbers.\n"
        "- If a protection relevant to the question is flagged MISSING in the "
        "compliance snapshot, say so explicitly and flag the risk.\n"
        "- If the retrieved text does not answer the question, say so and "
        "explain what standard wording would typically cover.\n"
        "- Do NOT add any legal disclaimer or warning — the page already shows "
        "one. Give the substantive answer.\n"
        "- Be CONCISE: at most ~130 words in short sections and bullets. Do NOT "
        "re-quote the retrieved clauses in full — cite them by number and "
        "section. No preamble, no repetition, no filler.\n\n"
        "=== RETRIEVED CLAUSES (verbatim) ===\n"
        f"{clause_text}\n=== END ===\n{snapshot}\n{legal_block}"
    ).format(question=question)

    chat_history = history + [{"role": "user", "content": prompt}]
    step("Writing your cited answer (IPC/BNS + clause numbers)", 0.55)
    answer = _chat(chat_history, system=SYSTEM_PROMPT,
                   num_predict=answer_tokens, temperature=0.4)
    step("Finalizing", 0.9)

    # Guarantee the requested legal citations are always present: the small
    # model may miss or mangle a statutor numbers, so the exact sections are
    # attached deterministically when this is a law question.
    if legal_md:
        answer = (
            answer.strip()
            + "\n\n#### Legal references (India)\n"
            + legal_md
        )

    citation_block = (
        f"> **Source clauses (retrieved by retrieve_contract_text):**\n"
        f">\n" + "\n".join(f"> {line}" for line in clause_text.strip().splitlines()[:60])
    )
    return answer, citation_block, chat_history + [{"role": "assistant", "content": answer}]