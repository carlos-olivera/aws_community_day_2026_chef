"""MockPlanner: deterministic, and the flaw triggers exactly one repair cycle."""

from rich.console import Console

from chef_andino.agent.runner import AgentRunner
from chef_andino.agent.trace import TraceWriter
from chef_andino.planner.mock import MockPlanner
from chef_andino.tools.factory import build_local_toolset

QUIET = Console(quiet=True)


def run_mission(store, settings, event_id, flaw):
    audits: list[dict] = []
    trace = TraceWriter(settings.runs_dir, QUIET)
    tools = build_local_toolset(
        store, settings, event_id, audit=lambda rec: (audits.append(rec), trace.audit_sink(rec))
    )
    planner = MockPlanner(first_candidate_flaw=flaw)
    result = AgentRunner(planner, tools, store, settings.budget, trace).run(event_id)
    return result, audits


def test_flawed_run_shows_deny_then_allow(store, frozen_event, settings):
    result, audits = run_mission(store, settings, frozen_event, "declared_allergen")
    assert result.published
    assert result.finish_reason == "published"
    effects = [a["effect"] for a in audits]
    assert effects == ["DENY", "ALLOW"]  # exactly one repair cycle


def test_clean_run_never_gets_denied(store, frozen_event, settings):
    result, audits = run_mission(store, settings, frozen_event, None)
    assert result.published
    assert [a["effect"] for a in audits] == ["ALLOW"]


def test_published_menu_is_deterministic(snapshot, inventory, corpus_pools):
    from chef_andino.planner.mock import assemble_menu

    args = (
        snapshot.model_dump(mode="json"),
        [i.model_dump(mode="json") for i in inventory],
        corpus_pools,
    )
    first = assemble_menu(*args)
    second = assemble_menu(*args)
    # Identical except the throwaway candidate id and timestamp.
    for menu in (first, second):
        menu.pop("menu_id"), menu.pop("generated_at")
    assert first == second


def test_flawed_first_candidate_contains_the_banned_dish(snapshot, inventory, corpus_pools):
    from chef_andino.planner.mock import assemble_menu

    menu = assemble_menu(
        snapshot.model_dump(mode="json"),
        [i.model_dump(mode="json") for i in inventory],
        corpus_pools,
        apply_allergen_filter=False,
    )
    assert menu["meals"]["lunch"]["starter"]["dish_id"] == "sopa_de_mani"
