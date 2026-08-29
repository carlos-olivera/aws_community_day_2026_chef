"""Event storage: a protocol plus a local JSON-file implementation.

Teaching concept: *ports and adapters*. The rest of the system depends only
on the :class:`~chef_andino.store.base.EventStore` protocol. Locally it is a
single pretty-printed JSON file you can open in an editor and watch change;
in the cloud phase the same protocol is backed by DynamoDB.
"""

from chef_andino.store.base import EventRecord, EventStore
from chef_andino.store.local_json import LocalJsonStore

__all__ = ["EventRecord", "EventStore", "LocalJsonStore"]
