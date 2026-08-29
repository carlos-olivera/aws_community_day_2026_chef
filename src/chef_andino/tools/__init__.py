"""The agent's six tools - "tools are the API of the agent's world".

Teaching concepts:

* *Ports and adapters*: each tool is a Protocol (the port) with a local
  adapter now and an AWS adapter in the cloud phase. The agent loop never
  changes when the backend does.
* *Semantic knowledge -> RAG, real state -> tools*: culinary know-how comes
  from a searchable corpus (:mod:`~chef_andino.tools.knowledge`); the actual
  stock of quinoa comes from a database (:mod:`~chef_andino.tools.inventory`).
* *Internet is inspiration, not authority*: if
  :mod:`~chef_andino.tools.web_research` fails, the mission still completes.

The factory :func:`build_local_toolset` wires the local adapters into a
:class:`~chef_andino.tools.base.ToolRegistry`.
"""

from chef_andino.tools.base import Tool, ToolRegistry, ToolResult
from chef_andino.tools.factory import build_local_toolset

__all__ = ["Tool", "ToolRegistry", "ToolResult", "build_local_toolset"]
