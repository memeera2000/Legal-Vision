import os
import re
import shutil
from pathlib import Path

from langchain_ollama import ChatOllama, OllamaEmbeddings
from langchain_community.document_loaders import PyPDFLoader, TextLoader
from langchain_core.documents import Document
from langchain_text_splitters import TextSplitter

CHROMA_DIR = Path(__file__).resolve().parent / "chroma_store"
TEMP_DIR = Path(__file__).resolve().parent / "temp"


# -------------------------------
# Clause-aware text splitter
# -------------------------------
class ClauseAwareSplitter(TextSplitter):
    """Splits legal documents on clause/section boundaries (numbered clauses)
    so a clause is never split across two chunks."""

    def __init__(self, chunk_size: int = 4000, min_chunk: int = 200, **kwargs):
        super().__init__(**kwargs)
        self.chunk_size = chunk_size
        self.min_chunk = min_chunk

    def _clause_boundaries(self, text: str) -> list[tuple[int, str]]:
        """Find positions where a new numbered clause/section begins."""
        patterns = [
            # Numbered clauses: "1. ", "1.1 ", "10. ", "3.2.1 "
            re.compile(r"(?m)^\s*(\d{1,3}(?:\.\d{1,3})*[\.\)])\s+\S"),
            # Explicit markers: SECTION x, ARTICLE x, CLAUSE x
            re.compile(r"(?m)^\s*(?:SECTION|ARTICLE|CLAUSE)\s+\d+(?:\.\d+)*[\.:\s]", re.IGNORECASE),
            # Roman-numeral clause headings on their own line: "I. ", "II. "
            re.compile(r"(?m)^\s*[IVX]{1,5}\.\s+\S"),
            # Capital-letter clause headings on their own line (TOS style): "A. "
            re.compile(r"(?m)^\s*[A-Z]\.\s+\S"),
        ]
        boundaries = []
        for pat in patterns:
            for m in pat.finditer(text):
                boundaries.append((m.start(), m.group(0).strip()))
        boundaries.sort()
        return boundaries

    def split_text(self, text: str) -> list[str]:
        boundaries = self._clause_boundaries(text)

        if not boundaries:
            # Fallback: sentence-level splitting with overlap to avoid losing context
            sentences = re.split(r'(?<=[.!?])\s+', text)
            chunks, buf, size = [], "", 0
            for s in sentences:
                if size + len(s) > self.chunk_size and buf:
                    chunks.append(buf.strip())
                    buf, size = s, len(s)
                else:
                    buf = f"{buf} {s}".strip()
                    size = len(buf)
            if buf.strip():
                chunks.append(buf.strip())
            return [c for c in chunks if len(c) >= self.min_chunk] or [text]

        # Split at boundaries; attach preamble (header/intro before first clause)
        start = 0
        chunks = []
        for pos, label in boundaries:
            preamble = text[start:pos].strip()
            if preamble and len(preamble) >= self.min_chunk:
                chunks.append(preamble)
            elif preamble and chunks:
                # tiny preamble — merge with next chunk instead of dropping it
                chunks[-1] += "\n\n" + preamble
            start = pos
        tail = text[start:].strip()
        if tail:
            chunks.append(tail)

        return [c for c in chunks if c.strip()]


# -------------------------------
# Document loading
# -------------------------------
def load_document(file_path: str) -> list[Document]:
    """Load a contract PDF or text/markdown file. Returns a list of Documents."""
    ext = Path(file_path).suffix.lower()
    if ext == ".pdf":
        loader = PyPDFLoader(file_path)
        pages = loader.load()
        # Join pages into one logical text for clause splitting
        full_text = "\n\n".join(p.page_content for p in pages)
        doc = Document(page_content=full_text, metadata={"source": file_path})
        return [doc]
    elif ext in (".txt", ".md", ".markdown"):
        loader = TextLoader(file_path, encoding="utf-8")
        return loader.load()
    else:
        raise ValueError(f"Unsupported file type: {ext}. Use .pdf, .txt, or .md.")


def split_clauses(docs: list[Document], chunk_size: int = 4000) -> list[Document]:
    """Split loaded documents into clause-boundary-preserving chunks."""
    splitter = ClauseAwareSplitter(chunk_size=chunk_size)
    chunks = []
    for i, doc in enumerate(docs):
        for j, text in enumerate(splitter.split_text(doc.page_content)):
            meta = dict(doc.metadata)
            meta["chunk_index"] = j
            chunks.append(Document(page_content=text, metadata=meta))
    # Order chunks by chunk_index for stable retrieval ordering tie-breaks
    chunks.sort(key=lambda d: d.metadata.get("chunk_index", 0))
    return chunks


# -------------------------------
# Embeddings + vector store
# -------------------------------
def build_embeddings(model: str = "nomic-embed-text", base_url: str = "http://localhost:11434"):
    return OllamaEmbeddings(model=model, base_url=base_url)


def get_vectorstore(
    chunks: list[Document],
    collection_name: str = "contract_rag",
    embedding_model: str = "nomic-embed-text",
    base_url: str = "http://localhost:11434",
    persist: bool = True,
):
    """Embed and persist chunks to Chroma. Returns the retriever and store."""
    from langchain_chroma import Chroma

    if persist:
        _clear_chroma(collection_name)

    embeddings = build_embeddings(embedding_model, base_url)

    vectorstore = Chroma.from_documents(
        documents=chunks,
        embedding=embeddings,
        collection_name=collection_name,
        persist_directory=str(CHROMA_DIR),
        collection_metadata={"hnsw:space": "cosine"},
    )
    return vectorstore


def load_vectorstore(
    collection_name: str = "contract_rag",
    embedding_model: str = "nomic-embed-text",
    base_url: str = "http://localhost:11434",
):
    from langchain_chroma import Chroma

    db = CHROMA_DIR / "chroma.sqlite3"
    if not db.exists() or db.stat().st_size == 0:
        # No ingest yet, or a killed engine left a truncated DB behind.
        _clear_chroma(collection_name)
        raise RuntimeError("No analyzed contract yet — upload a document first.")
    try:
        embeddings = build_embeddings(embedding_model, base_url)
        return Chroma(
            collection_name=collection_name,
            embedding_function=embeddings,
            persist_directory=str(CHROMA_DIR),
            collection_metadata={"hnsw:space": "cosine"},
        )
    except Exception:
        # Corrupt store (e.g. interrupted write): wiping lets the next upload
        # rebuild cleanly instead of surfacing 'no such table: tenants'.
        _clear_chroma(collection_name)
        raise RuntimeError(
            "The analyzed-contract store was corrupt and has been reset. "
            "Please upload the document again."
        )


def _clear_chroma(collection_name: str):
    if CHROMA_DIR.exists():
        shutil.rmtree(CHROMA_DIR, ignore_errors=True)


def build_retriever(
    vectorstore,
    k: int = 3,
):
    """Create a similarity retriever that returns the most relevant clause chunks."""
    return vectorstore.as_retriever(
        search_type="similarity",
        search_kwargs={"k": k},
    )


# -------------------------------
# One-call ingestion into RAG
# -------------------------------
def ingest_contract(file_path: str, **kwargs) -> dict:
    """Full pipeline: load -> clause-split -> embed -> persist -> retriever.
    Returns dict with docs, chunks, vectorstore, retriever."""
    docs = load_document(file_path)
    chunks = split_clauses(docs)
    vectorstore = get_vectorstore(chunks, **kwargs)
    retriever = build_retriever(vectorstore)
    return {
        "docs": docs,
        "chunks": chunks,
        "vectorstore": vectorstore,
        "retriever": retriever,
    }