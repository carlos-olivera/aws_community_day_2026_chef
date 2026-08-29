"""Each local tool adapter behaves as its port promises."""

from chef_andino.tools.factory import build_local_toolset
from chef_andino.tools.knowledge import LocalCorpusSearch


def test_registry_exposes_exactly_six_tools(store, frozen_event, settings):
    tools = build_local_toolset(store, settings, frozen_event)
    assert tools.names() == sorted(
        [
            "get_event_snapshot",
            "get_available_ingredients",
            "search_culinary_knowledge",
            "research_web",
            "evaluate_menu",
            "validate_and_publish_menu",
        ]
    )


def test_snapshot_tool_returns_the_frozen_aggregate(store, frozen_event, settings):
    tools = build_local_toolset(store, settings, frozen_event)
    result = tools.get("get_event_snapshot").fn()
    assert result.ok
    assert result.data["snapshot_version"] == 1
    assert result.data["total_responses"] == 40


def test_snapshot_tool_fails_before_freeze(store, seeded_event, settings):
    tools = build_local_toolset(store, settings, seeded_event)
    result = tools.get("get_event_snapshot").fn()
    assert not result.ok
    assert "freeze" in result.error


def test_inventory_tool_lists_validated_items(store, frozen_event, settings):
    result = build_local_toolset(store, settings, frozen_event).get(
        "get_available_ingredients"
    ).fn()
    assert result.ok
    ids = {item["ingredient_id"] for item in result.data}
    assert {"quinoa", "potato", "peanut", "trout"} <= ids


def test_knowledge_search_ranks_by_relevance(settings):
    search = LocalCorpusSearch(settings.corpus_dir)
    hits = search.search("quinoa soup", filters={"type": "dish", "course": "starter"})
    assert hits[0].doc_id == "dishes/sopa_de_quinua"


def test_knowledge_search_filters_by_metadata(settings):
    search = LocalCorpusSearch(settings.corpus_dir)
    hits = search.search("", filters={"type": "dish", "course": "dessert"})
    assert hits and all(h.metadata["course"] == "dessert" for h in hits)
    vegan_hits = search.search(
        "", filters={"type": "dish", "course": "main", "dietary_flags": "vegan"}
    )
    assert vegan_hits and all("vegan" in h.metadata["dietary_flags"] for h in vegan_hits)


def test_web_research_is_canned_and_harmless(store, frozen_event, settings):
    result = build_local_toolset(store, settings, frozen_event).get("research_web").fn(
        query="anything at all"
    )
    assert result.ok
    assert all("canned" in r["title"] for r in result.data)


def test_bedrock_toolspec_projection(store, frozen_event, settings):
    specs = build_local_toolset(store, settings, frozen_event).as_bedrock_toolspecs()
    assert len(specs) == 6
    spec = next(s for s in specs if s["toolSpec"]["name"] == "search_culinary_knowledge")
    assert "query" in spec["toolSpec"]["inputSchema"]["json"]["properties"]
