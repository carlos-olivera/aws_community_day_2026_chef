"""The ``chef`` command line: the whole demo without leaving the terminal.

chef seed          load synthetic responses + create the event
chef stats         live aggregate counters (what the dashboard shows)
chef freeze        close the survey and take snapshot v1
chef run-agent     run Chef Andino (mock planner by default)
chef show-menu     pretty-print the published menu
chef demo-governance   the explicit policy DENY -> ALLOW demo
chef serve         start the local FastAPI backend for the web UI
chef reset         wipe .localdata/ and start over
"""

from __future__ import annotations

import json

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from chef_andino.config import DEFAULT_EVENT_ID, Settings
from chef_andino.contracts.models import SurveyResponse
from chef_andino.lifecycle.aggregate import build_snapshot
from chef_andino.lifecycle.states import EventState, transition
from chef_andino.store.local_json import LocalJsonStore

app = typer.Typer(help=__doc__, no_args_is_help=True, add_completion=False)
console = Console()


def _store(settings: Settings) -> LocalJsonStore:
    return LocalJsonStore(settings.db_path)


@app.command()
def seed(event: str = DEFAULT_EVENT_ID) -> None:
    """Create the event and load the synthetic survey responses."""
    settings = Settings()
    store = _store(settings)
    store.create_event(event)
    raw = json.loads(settings.responses_path.read_text())
    for item in raw:
        item["event_id"] = event
        store.add_response(SurveyResponse.model_validate(item))
    console.print(f"[green]seeded[/green] event '{event}' with {len(raw)} responses")


@app.command()
def stats(event: str = DEFAULT_EVENT_ID) -> None:
    """Show live aggregate counters - exactly what the dashboard displays."""
    settings = Settings()
    store = _store(settings)
    responses = store.list_responses(event)
    record = store.get_event(event)
    if not responses:
        console.print("no responses yet")
        return
    # A preview aggregate for display only - never stored as a real snapshot.
    snap = build_snapshot(event, responses, version=1)
    table = Table(title=f"{event} - {record.state.value} - {len(responses)} responses")
    table.add_column("metric")
    table.add_column("value")
    table.add_row("diets", str(snap.diet_counts))
    table.add_row("lactose intolerant", str(snap.lactose_intolerant_count))
    table.add_row("gluten free", str(snap.gluten_free_count))
    table.add_row("declared allergens", str(snap.allergen_counts))
    table.add_row("spice", str(snap.spice_counts))
    table.add_row("max default spice", snap.derived_constraints.max_default_spice)
    table.add_row(
        "top ingredients",
        ", ".join(f"{c.ingredient}({c.count})" for c in snap.top_preferred_ingredients),
    )
    console.print(table)


@app.command()
def freeze(event: str = DEFAULT_EVENT_ID) -> None:
    """Close the survey: OPEN -> FROZEN, and write the immutable snapshot."""
    settings = Settings()
    store = _store(settings)
    responses = store.list_responses(event)
    version = store.get_event(event).latest_snapshot_version + 1
    transition(store, event, EventState.FROZEN)
    store.save_snapshot(build_snapshot(event, responses, version))
    console.print(
        f"[cyan]frozen[/cyan] event '{event}' - snapshot v{version} "
        f"({len(responses)} responses)"
    )


@app.command("run-agent")
def run_agent(
    event: str = DEFAULT_EVENT_ID,
    planner: str = typer.Option("mock", help="mock | bedrock"),
    flaw: bool = typer.Option(
        True, help="Inject a first-candidate flaw so the run shows DENY -> repair."
    ),
) -> None:
    """Give Chef Andino its mission: design and publish the event menu."""
    from chef_andino.agent.runner import AgentRunner
    from chef_andino.agent.trace import TraceWriter
    from chef_andino.tools.factory import build_local_toolset

    settings = Settings()
    store = _store(settings)
    trace = TraceWriter(settings.runs_dir, console)
    tools = build_local_toolset(store, settings, event, audit=trace.audit_sink)

    if planner == "mock":
        from chef_andino.planner.mock import MockPlanner

        brain = MockPlanner(first_candidate_flaw="declared_allergen" if flaw else None)
    elif planner == "bedrock":
        from chef_andino.planner.bedrock import BedrockPlanner

        brain = BedrockPlanner(tools)
        console.print("[yellow]real-LLM mode: this call costs money[/yellow]")
    else:
        raise typer.BadParameter("planner must be 'mock' or 'bedrock'")

    console.print(Panel.fit(f"CHEF ANDINO - RUNNING ({planner} planner)"))
    result = AgentRunner(brain, tools, store, settings.budget, trace).run(event)
    colour = "green" if result.published else "red"
    console.print(
        f"[{colour}]run {result.run_id}: published={result.published} "
        f"steps={result.steps} reason={result.finish_reason}[/{colour}]"
    )
    console.print(f"trace: {trace.run_dir / 'trace.jsonl'}")
    raise typer.Exit(0 if result.published else 1)


@app.command("show-menu")
def show_menu(event: str = DEFAULT_EVENT_ID) -> None:
    """Pretty-print the published menu, coverage and disclaimer."""
    settings = Settings()
    menu = _store(settings).get_menu(event)
    if menu is None:
        console.print("[red]no published menu yet - run `chef run-agent` first[/red]")
        raise typer.Exit(1)

    def dish_line(item) -> str:
        flags = ",".join(item.dietary_flags) or "-"
        return f"[bold]{item.name}[/bold] [dim]({flags})[/dim]"

    lines = ["[u]BREAKFAST - BUFFET[/u]"]
    lines += [f"  - {dish_line(i)}" for i in menu.meals.breakfast.items]
    lines += ["", "[u]LUNCH[/u]", f"  starter: {dish_line(menu.meals.lunch.starter)}"]
    lines += [f"  main:    {dish_line(m)}" for m in menu.meals.lunch.mains]
    lines += [f"  dessert: {dish_line(menu.meals.lunch.dessert)}"]
    lines += ["", "[u]DINNER[/u]", f"  main:    {dish_line(menu.meals.dinner.main)}"]
    lines += [f"  dessert: {dish_line(menu.meals.dinner.dessert)}"]
    if menu.coverage:
        cov = menu.coverage
        lines += [
            "",
            f"vegetarian lunch main: {cov.vegetarian_lunch_main}  "
            f"vegan/meal: {cov.vegan_option_per_meal}  "
            f"gf/meal: {cov.gluten_free_option_per_meal}  "
            f"lf/meal: {cov.lactose_free_option_per_meal}",
            f"bolivian ingredient ratio: {cov.bolivian_ingredient_ratio}",
        ]
    lines += ["", f"[dim]{menu.disclaimer}[/dim]"]
    console.print(Panel("\n".join(lines), title=f"MENU - {event} (menu {menu.menu_id})"))


@app.command("demo-governance")
def demo_governance(event: str = DEFAULT_EVENT_ID) -> None:
    """Show policy in action: a bypass attempt is DENIED, the honest path is ALLOWED.

    Requires a FROZEN event (freeze first, do not run the agent).
    """
    from chef_andino.agent.trace import TraceWriter
    from chef_andino.planner.mock import assemble_menu
    from chef_andino.policy.engine import LocalPolicyEngine
    from chef_andino.tools.factory import build_local_toolset
    from chef_andino.tools.inventory import LocalInventorySource
    from chef_andino.tools.publish import MenuPublisher

    settings = Settings()
    store = _store(settings)
    trace = TraceWriter(settings.runs_dir, console)
    transition(store, event, EventState.GENERATING)

    # Reuse the mock planner's assembler to build a perfectly valid menu.
    tools = build_local_toolset(store, settings, event, audit=trace.audit_sink)
    snapshot = tools.get("get_event_snapshot").fn().data
    inventory = tools.get("get_available_ingredients").fn().data
    pools = {}
    for course in ("breakfast", "starter", "main", "dessert"):
        hits = tools.get("search_culinary_knowledge").fn(
            query="", filters={"type": "dish", "course": course}
        ).data
        pools[course] = [
            h["metadata"] | {"doc_id": h["doc_id"], "snippet": h["snippet"]} for h in hits
        ]
    menu = assemble_menu(snapshot, inventory, pools)

    publisher = MenuPublisher(
        store, LocalPolicyEngine(), LocalInventorySource(settings.inventory_path),
        event, audit=trace.audit_sink,
    )

    console.print(Panel.fit("ATTEMPT 1: publish while SKIPPING validation"))
    denied = publisher.validate_and_publish(menu, skip_validation=True)
    console.print(f"  result: ok={denied.ok}  [red]{denied.error}[/red]")

    console.print(Panel.fit("ATTEMPT 2: validate first, then publish"))
    allowed = publisher.validate_and_publish(menu)
    console.print(f"  result: ok={allowed.ok}  data={allowed.data}")
    console.print(f"audit log: {trace.run_dir / 'audit.jsonl'}")


@app.command()
def serve(host: str = "127.0.0.1", port: int = 8000) -> None:
    """Start the local FastAPI backend (the web UI's API)."""
    import uvicorn

    uvicorn.run("chef_andino.api.app:app", host=host, port=port, reload=False)


@app.command()
def reset(yes: bool = typer.Option(False, "--yes", help="Skip confirmation.")) -> None:
    """Delete .localdata/ (events, runs, menus) and start over."""
    import shutil

    settings = Settings()
    if not yes:
        typer.confirm(f"delete {settings.local_dir}?", abort=True)
    shutil.rmtree(settings.local_dir, ignore_errors=True)
    console.print("[green]local state wiped[/green]")


if __name__ == "__main__":
    app()
