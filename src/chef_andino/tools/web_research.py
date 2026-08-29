"""Tool 4/6: ``research_web`` - the internet as inspiration, never authority.

Design rule from the talk: if web research fails, Chef Andino still finishes
its mission; if the knowledge base fails, it must not. The backbone ships a
canned offline adapter so the budget (max 3 queries) and the tool shape are
demonstrable with zero network. The cloud phase swaps in AgentCore
Browser / Web Search behind the same port.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from chef_andino.tools.base import Tool, ToolResult


@dataclass
class WebResult:
    """One (pretend) search result."""

    title: str
    url: str
    summary: str


class WebResearch(Protocol):
    """Port: anything that can look something up "out there"."""

    def search(self, query: str) -> list[WebResult]:
        """Return complementary inspiration for a query."""
        ...


class CannedWebResearch:
    """Adapter: fixed offline results - honest about being canned."""

    _CANNED = [
        WebResult(
            title="Buffet planning for large events (canned result)",
            url="https://example.com/buffet-planning",
            summary=(
                "Large-event buffets favour dishes that hold temperature well, "
                "are self-served easily and avoid cross-contamination between "
                "stations."
            ),
        ),
        WebResult(
            title="Andean grains in modern menus (canned result)",
            url="https://example.com/andean-grains",
            summary=(
                "Quinoa, amaranth and cañahua adapt well to both savoury mains "
                "and desserts, and are naturally gluten-free."
            ),
        ),
    ]

    def search(self, query: str) -> list[WebResult]:
        """Return the same two inspiration snippets for any query."""
        return list(self._CANNED)


def make_web_research_tool(source: WebResearch) -> Tool:
    """Wrap the port as a named tool."""

    def fn(query: str = "") -> ToolResult:
        results = source.search(query)
        return ToolResult(
            ok=True,
            data=[{"title": r.title, "url": r.url, "summary": r.summary} for r in results],
        )

    return Tool(
        name="research_web",
        description=(
            "OPTIONAL complementary web research for inspiration. Never use "
            "this as the source of truth for ingredients or constraints."
        ),
        args_schema={
            "type": "object",
            "properties": {"query": {"type": "string"}},
        },
        fn=fn,
    )
