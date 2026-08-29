"""Tool 3/6: ``search_culinary_knowledge`` - the RAG stand-in.

Local adapter: a deliberately naive, readable search over the markdown
corpus in ``data/corpus/`` (metadata filter first, then keyword ranking).
Cloud adapter (later phase): Amazon Bedrock Knowledge Bases + S3 Vectors,
behind the exact same port - same interface, different retrieval engine.

Corpus layout (see docs/corpus-guide.md): every document is a ``slug.md``
file with a sibling ``slug.meta.json`` carrying filterable attributes -
mirroring Bedrock Knowledge Bases' filterable metadata feature.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from chef_andino.tools.base import Tool, ToolResult

DEFAULT_TOP_K = 5


@dataclass
class KnowledgeHit:
    """One retrieved document."""

    doc_id: str        # e.g. "dishes/sopa_de_quinua"
    title: str
    snippet: str       # first paragraph of the markdown body
    metadata: dict
    score: float


class CulinaryKnowledge(Protocol):
    """Port: anything that can retrieve culinary know-how."""

    def search(self, query: str, filters: dict | None = None) -> list[KnowledgeHit]:
        """Return the best-matching documents for a query + metadata filters."""
        ...


def _matches_filters(metadata: dict, filters: dict) -> bool:
    """True when every filter key is satisfied by the document's metadata.

    Rules (kept simple on purpose):
    * filter value is a list  -> metadata value must overlap it
    * metadata value is a list -> it must contain the filter value
    * both scalars            -> plain equality
    """
    for key, wanted in filters.items():
        actual = metadata.get(key)
        wanted_set = set(wanted) if isinstance(wanted, list) else {wanted}
        actual_set = set(actual) if isinstance(actual, list) else {actual}
        if not wanted_set & actual_set:
            return False
    return True


def _tokens(text: str) -> set[str]:
    return set(re.findall(r"[a-záéíóúñü]+", text.lower()))


class LocalCorpusSearch:
    """Adapter: filter-then-rank over the local markdown corpus."""

    def __init__(self, corpus_dir: Path) -> None:
        """Load every document into memory (the corpus is small on purpose)."""
        self._docs: list[KnowledgeHit] = []
        for md_path in sorted(corpus_dir.rglob("*.md")):
            meta_path = md_path.with_suffix("").with_suffix(".meta.json")
            metadata = json.loads(meta_path.read_text()) if meta_path.exists() else {}
            body = md_path.read_text()
            first_paragraph = next(
                (p.strip() for p in body.split("\n\n") if p.strip() and not p.startswith("#")),
                "",
            )
            self._docs.append(
                KnowledgeHit(
                    doc_id=str(md_path.relative_to(corpus_dir).with_suffix("")),
                    title=metadata.get("name", md_path.stem),
                    snippet=first_paragraph[:300],
                    metadata=metadata,
                    score=0.0,
                )
            )

    def search(self, query: str, filters: dict | None = None) -> list[KnowledgeHit]:
        """Metadata filter first, keyword-overlap ranking second."""
        candidates = [
            doc for doc in self._docs
            if not filters or _matches_filters(doc.metadata, filters)
        ]
        query_tokens = _tokens(query)
        scored: list[KnowledgeHit] = []
        for doc in candidates:
            doc_tokens = (
                _tokens(doc.title)
                | _tokens(" ".join(doc.metadata.get("tags", [])))
                | _tokens(doc.snippet)
            )
            overlap = len(query_tokens & doc_tokens)
            score = overlap / len(query_tokens) if query_tokens else 0.0
            scored.append(
                KnowledgeHit(doc.doc_id, doc.title, doc.snippet, doc.metadata, score)
            )
        scored.sort(key=lambda h: (-h.score, h.doc_id))
        return scored[:DEFAULT_TOP_K] if query_tokens else scored


def make_knowledge_tool(source: CulinaryKnowledge) -> Tool:
    """Wrap the port as a named tool."""

    def fn(query: str = "", filters: dict | None = None) -> ToolResult:
        hits = source.search(query, filters)
        return ToolResult(
            ok=True,
            data=[
                {
                    "doc_id": h.doc_id,
                    "title": h.title,
                    "snippet": h.snippet,
                    "metadata": h.metadata,
                    "score": round(h.score, 3),
                }
                for h in hits
            ],
        )

    return Tool(
        name="search_culinary_knowledge",
        description=(
            "Search the curated Bolivian culinary knowledge base. Supports a "
            "free-text query plus metadata filters such as "
            '{"type": "dish", "course": "main", "dietary_flags": "vegan"}.'
        ),
        args_schema={
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "filters": {"type": "object"},
            },
        },
        fn=fn,
    )
