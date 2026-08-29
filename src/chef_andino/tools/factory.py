"""Wire the local adapters into the agent's ToolRegistry.

The cloud phase adds a ``build_aws_toolset`` sibling that returns the same
six tool names backed by DynamoDB, Bedrock Knowledge Bases, web search and
a Lambda behind AgentCore Gateway - and the agent loop will not notice.
"""

from __future__ import annotations

from chef_andino.config import Settings
from chef_andino.policy.engine import LocalPolicyEngine
from chef_andino.store.base import EventStore
from chef_andino.tools.base import ToolRegistry
from chef_andino.tools.evaluate import make_evaluate_tool
from chef_andino.tools.inventory import LocalInventorySource, make_inventory_tool
from chef_andino.tools.knowledge import LocalCorpusSearch, make_knowledge_tool
from chef_andino.tools.publish import AuditSink, MenuPublisher, make_publish_tool
from chef_andino.tools.snapshot import LocalSnapshotSource, make_snapshot_tool
from chef_andino.tools.web_research import CannedWebResearch, make_web_research_tool


def build_local_toolset(
    store: EventStore,
    settings: Settings,
    event_id: str,
    audit: AuditSink = lambda record: None,
) -> ToolRegistry:
    """Return the six tools, all backed by local adapters, bound to one event."""
    snapshot_source = LocalSnapshotSource(store)
    inventory_source = LocalInventorySource(settings.inventory_path)
    publisher = MenuPublisher(
        store=store,
        policy=LocalPolicyEngine(),
        inventory=inventory_source,
        event_id=event_id,
        audit=audit,
    )
    return ToolRegistry(
        [
            make_snapshot_tool(snapshot_source, event_id),
            make_inventory_tool(inventory_source),
            make_knowledge_tool(LocalCorpusSearch(settings.corpus_dir)),
            make_web_research_tool(CannedWebResearch()),
            make_evaluate_tool(
                snapshot_getter=lambda: snapshot_source.get(event_id),
                inventory_getter=inventory_source.list,
            ),
            make_publish_tool(publisher),
        ]
    )
