"""DynamoDB adapters used by the deployed Chef Andino demonstration.

The cloud data model deliberately keeps one small event document with live
aggregates and stores anonymous responses separately.  A reset increments the
cycle, so the public URL never changes and old data can expire asynchronously.
"""

from __future__ import annotations

import hashlib
import json
import random
import time
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from chef_andino.contracts.models import (
    Allergen,
    CuisinePreference,
    DerivedConstraints,
    Diet,
    EventSnapshot,
    IngredientCount,
    InventoryItem,
    PreferredIngredient,
    SpiceLevel,
    SurveyResponse,
)
from chef_andino.lifecycle.states import EventState

DIETS: tuple[Diet, ...] = ("none", "vegetarian", "vegan")
ALLERGENS: tuple[Allergen, ...] = (
    "peanut",
    "tree_nuts",
    "shellfish",
    "fish",
    "egg",
    "soy",
)
SPICE_LEVELS: tuple[SpiceLevel, ...] = ("mild", "medium", "hot")
CUISINES: tuple[CuisinePreference, ...] = (
    "traditional_bolivian",
    "andean_fusion",
    "international",
    "no_preference",
)
PREFERRED_INGREDIENTS: tuple[PreferredIngredient, ...] = (
    "quinoa",
    "potato",
    "corn",
    "aji_amarillo",
    "llama_meat",
    "trout",
    "chuno",
    "broad_beans",
    "amaranth",
    "peanut",
)
TRANSACTION_ATTEMPTS = 24
COUNTER_SHARDS = 32


class CloudConflict(RuntimeError):
    """The requested operation conflicts with the current event state."""


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _plain(value: Any) -> Any:
    """Convert DynamoDB Decimals into ordinary JSON-compatible numbers."""
    if isinstance(value, Decimal):
        return int(value) if value == value.to_integral_value() else float(value)
    if isinstance(value, dict):
        return {key: _plain(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_plain(item) for item in value]
    return value


def _ddb(value: Any) -> Any:
    """Convert floats to Decimal so boto3's DynamoDB resource accepts them."""
    return json.loads(json.dumps(value, default=str), parse_float=Decimal)


def initial_event(event_id: str, cycle: int = 1) -> dict[str, Any]:
    """Return the complete, update-friendly shape of a fresh event cycle."""
    return {
        "event_id": event_id,
        "cycle": cycle,
        "state": EventState.OPEN.value,
        "created_at": _utcnow(),
        "updated_at": _utcnow(),
        "total_responses": 0,
        "diet_counts": {key: 0 for key in DIETS},
        "allergen_counts": {key: 0 for key in ALLERGENS},
        "spice_counts": {key: 0 for key in SPICE_LEVELS},
        "cuisine_counts": {key: 0 for key in CUISINES},
        "ingredient_counts": {key: 0 for key in PREFERRED_INGREDIENTS},
        "lactose_intolerant_count": 0,
        "gluten_free_count": 0,
    }


def snapshot_from_event(item: dict[str, Any]) -> EventSnapshot:
    """Build the immutable aggregate directly from transactionally kept counters."""
    item = _plain(item)
    total = int(item["total_responses"])
    if total < 1:
        raise ValueError("no se puede congelar un evento sin respuestas")
    diets = {key: int(item["diet_counts"].get(key, 0)) for key in DIETS}
    allergens = {
        key: int(item["allergen_counts"].get(key, 0))
        for key in ALLERGENS
        if int(item["allergen_counts"].get(key, 0)) > 0
    }
    spices = {key: int(item["spice_counts"].get(key, 0)) for key in SPICE_LEVELS}
    cuisines = {key: int(item["cuisine_counts"].get(key, 0)) for key in CUISINES}
    preferred = sorted(
        (
            (key, int(item["ingredient_counts"].get(key, 0)))
            for key in PREFERRED_INGREDIENTS
            if int(item["ingredient_counts"].get(key, 0)) > 0
        ),
        key=lambda pair: (-pair[1], pair[0]),
    )[:5]

    max_spice: SpiceLevel = "mild"
    if (spices["medium"] + spices["hot"]) / total >= 0.9:
        max_spice = "medium"
    if spices["hot"] / total >= 0.9:
        max_spice = "hot"
    vegetarian_present = diets["vegetarian"] + diets["vegan"] > 0

    return EventSnapshot(
        event_id=item["event_id"],
        snapshot_version=int(item["cycle"]),
        created_at=datetime.now(timezone.utc),
        total_responses=total,
        diet_counts=diets,
        lactose_intolerant_count=int(item["lactose_intolerant_count"]),
        gluten_free_count=int(item["gluten_free_count"]),
        allergen_counts=allergens,
        spice_counts=spices,
        cuisine_counts=cuisines,
        top_preferred_ingredients=[
            IngredientCount(ingredient=key, count=count) for key, count in preferred
        ],
        derived_constraints=DerivedConstraints(
            must_exclude_allergens=sorted(allergens),
            require_vegetarian_lunch_main=vegetarian_present,
            require_vegan_option_per_meal=diets["vegan"] > 0,
            require_gluten_free_option_per_meal=int(item["gluten_free_count"]) > 0,
            require_lactose_free_option_per_meal=(int(item["lactose_intolerant_count"]) > 0),
            max_default_spice=max_spice,
        ),
    )


class DynamoCloudStore:
    """Operations required by the HTTP API, worker, and Gateway tools."""

    def __init__(
        self,
        events_table: str,
        responses_table: str,
        inventory_table: str,
        *,
        dynamodb_resource: Any | None = None,
        dynamodb_client: Any | None = None,
    ) -> None:
        """Connect to the three DynamoDB tables named in Lambda configuration."""
        if dynamodb_resource is None or dynamodb_client is None:
            import boto3

            dynamodb_resource = dynamodb_resource or boto3.resource("dynamodb")
            dynamodb_client = dynamodb_client or boto3.client("dynamodb")
        self.events_name = events_table
        self.responses_name = responses_table
        self.inventory_name = inventory_table
        self.events = dynamodb_resource.Table(events_table)
        self.responses = dynamodb_resource.Table(responses_table)
        self.inventory = dynamodb_resource.Table(inventory_table)
        self.client = dynamodb_client

    def ensure_event(self, event_id: str) -> dict[str, Any]:
        """Create the first OPEN cycle if it does not already exist."""
        created = False
        try:
            self.events.put_item(
                Item=_ddb(initial_event(event_id)),
                ConditionExpression="attribute_not_exists(event_id)",
            )
            created = True
        except self.client.exceptions.ConditionalCheckFailedException:
            pass
        item = self.get_event(event_id)
        if created:
            self._initialize_counter_shards(event_id, int(item["cycle"]))
        return item

    def get_event(self, event_id: str, *, consistent: bool = True) -> dict[str, Any]:
        """Return one event item or raise KeyError."""
        response = self.events.get_item(Key={"event_id": event_id}, ConsistentRead=consistent)
        if "Item" not in response:
            raise KeyError(event_id)
        return _plain(response["Item"])

    @staticmethod
    def _shard_key(event_id: str, cycle: int, shard: int) -> str:
        return f"{event_id}#counter#{cycle}#{shard:02d}"

    def _initialize_counter_shards(self, event_id: str, cycle: int) -> None:
        """Create the OPEN counter partitions before exposing a new cycle."""
        with self.events.batch_writer(overwrite_by_pkeys=["event_id"]) as batch:
            for shard in range(COUNTER_SHARDS):
                batch.put_item(
                    Item={
                        "event_id": self._shard_key(event_id, cycle, shard),
                        "cycle": cycle,
                        "state": EventState.OPEN.value,
                        "updated_at": _utcnow(),
                    }
                )

    def _aggregate_event(self, item: dict[str, Any]) -> dict[str, Any]:
        """Merge the active cycle's sharded counters into an event document."""
        from boto3.dynamodb.types import TypeDeserializer, TypeSerializer

        serializer = TypeSerializer()
        deserializer = TypeDeserializer()
        keys = [
            {
                "event_id": serializer.serialize(
                    self._shard_key(item["event_id"], int(item["cycle"]), shard)
                )
            }
            for shard in range(COUNTER_SHARDS)
        ]
        result = self.client.batch_get_item(
            RequestItems={
                self.events_name: {
                    "Keys": keys,
                    "ConsistentRead": True,
                }
            }
        )
        raw_shards = result.get("Responses", {}).get(self.events_name, [])
        shards = [
            _plain({key: deserializer.deserialize(value) for key, value in raw.items()})
            for raw in raw_shards
        ]
        merged = _plain(item)
        for shard in shards:
            merged["total_responses"] += int(shard.get("total_responses", 0))
            merged["lactose_intolerant_count"] += int(shard.get("lactose_intolerant_count", 0))
            merged["gluten_free_count"] += int(shard.get("gluten_free_count", 0))
            for key in DIETS:
                merged["diet_counts"][key] += int(shard.get(f"diet_{key}", 0))
            for key in ALLERGENS:
                merged["allergen_counts"][key] += int(shard.get(f"allergen_{key}", 0))
            for key in SPICE_LEVELS:
                merged["spice_counts"][key] += int(shard.get(f"spice_{key}", 0))
            for key in CUISINES:
                merged["cuisine_counts"][key] += int(shard.get(f"cuisine_{key}", 0))
            for key in PREFERRED_INGREDIENTS:
                merged["ingredient_counts"][key] += int(shard.get(f"ingredient_{key}", 0))
        return merged

    def reset(self, event_id: str) -> dict[str, Any]:
        """Open a clean cycle while allowing old responses to expire by TTL."""
        current = self.ensure_event(event_id)
        fresh = initial_event(event_id, int(current["cycle"]) + 1)
        self._initialize_counter_shards(event_id, fresh["cycle"])
        self.events.put_item(Item=_ddb(fresh))
        return fresh

    def submit_response(
        self, response: SurveyResponse, idempotency_key: str, *, ttl_hours: int = 48
    ) -> bool:
        """Store one response and update counters atomically.

        Returns ``False`` when the same idempotency key has already committed.
        """
        event = self.ensure_event(response.event_id)
        cycle = int(event["cycle"])
        response_id = hashlib.sha256(idempotency_key.encode()).hexdigest()[:32]
        event_cycle = f"{response.event_id}#{cycle}"
        item = response.model_copy(update={"response_id": response_id}).model_dump(mode="json")
        item |= {
            "event_cycle": event_cycle,
            "cycle": cycle,
            "expires_at": int(time.time()) + ttl_hours * 3600,
        }

        names: dict[str, str] = {
            "#state": "state",
            "#cycle": "cycle",
            "#total": "total_responses",
            "#updated": "updated_at",
            "#diet": f"diet_{response.diet}",
            "#spice": f"spice_{response.spice_level}",
            "#cuisine": f"cuisine_{response.cuisine_preference}",
        }
        adds = ["#total :one", "#diet :one", "#spice :one", "#cuisine :one"]
        if response.lactose_intolerant:
            names["#lactose"] = "lactose_intolerant_count"
            adds.append("#lactose :one")
        if response.gluten_free:
            names["#gluten"] = "gluten_free_count"
            adds.append("#gluten :one")
        for index, allergen in enumerate(response.allergies):
            names[f"#allergen_{index}"] = f"allergen_{allergen}"
            adds.append(f"#allergen_{index} :one")
        for index, ingredient in enumerate(response.preferred_ingredients):
            names[f"#ingredient_{index}"] = f"ingredient_{ingredient}"
            adds.append(f"#ingredient_{index} :one")

        from boto3.dynamodb.types import TypeSerializer

        serializer = TypeSerializer()
        shard = int(response_id[:8], 16) % COUNTER_SHARDS
        shard_key = self._shard_key(response.event_id, cycle, shard)
        transaction = [
            {
                "Put": {
                    "TableName": self.responses_name,
                    "Item": {key: serializer.serialize(value) for key, value in _ddb(item).items()},
                    "ConditionExpression": "attribute_not_exists(response_id)",
                }
            },
            {
                "Update": {
                    "TableName": self.events_name,
                    "Key": {"event_id": serializer.serialize(shard_key)},
                    "UpdateExpression": "SET #updated = :updated ADD " + ", ".join(adds),
                    "ConditionExpression": "#state = :open AND #cycle = :cycle_value",
                    "ExpressionAttributeNames": names,
                    "ExpressionAttributeValues": {
                        ":one": serializer.serialize(1),
                        ":updated": serializer.serialize(_utcnow()),
                        ":open": serializer.serialize(EventState.OPEN.value),
                        ":cycle_value": serializer.serialize(cycle),
                    },
                }
            },
        ]
        for attempt in range(TRANSACTION_ATTEMPTS):
            try:
                self.client.transact_write_items(TransactItems=transaction)
                return True
            except self.client.exceptions.TransactionConflictException:
                if attempt == TRANSACTION_ATTEMPTS - 1:
                    raise
                # Full jitter prevents concurrent voters from retrying in lock-step
                # against the same aggregate event item.
                time.sleep(random.uniform(0, min(0.4, 0.005 * (2**attempt))))
            except self.client.exceptions.TransactionCanceledException as exc:
                duplicate = self.responses.get_item(
                    Key={"event_cycle": event_cycle, "response_id": response_id},
                    ConsistentRead=True,
                ).get("Item")
                if duplicate:
                    return False
                current = self.get_event(response.event_id)
                if current["state"] != EventState.OPEN.value or int(current["cycle"]) != cycle:
                    raise CloudConflict("la encuesta está cerrada") from exc
                if attempt == TRANSACTION_ATTEMPTS - 1:
                    raise
                time.sleep(random.uniform(0, min(0.4, 0.005 * (2**attempt))))
        raise RuntimeError("se agotaron los reintentos de DynamoDB")

    def _close_counter_shards(self, event_id: str, cycle: int) -> None:
        """Atomically close the event document and every counter partition."""
        from boto3.dynamodb.types import TypeSerializer

        serializer = TypeSerializer()
        keys = [event_id] + [
            self._shard_key(event_id, cycle, shard) for shard in range(COUNTER_SHARDS)
        ]
        transaction = [
            {
                "Update": {
                    "TableName": self.events_name,
                    "Key": {"event_id": serializer.serialize(key)},
                    "UpdateExpression": "SET #state = :frozen, #updated = :updated",
                    "ConditionExpression": "#state = :open AND #cycle = :cycle",
                    "ExpressionAttributeNames": {
                        "#state": "state",
                        "#cycle": "cycle",
                        "#updated": "updated_at",
                    },
                    "ExpressionAttributeValues": {
                        ":open": serializer.serialize(EventState.OPEN.value),
                        ":frozen": serializer.serialize(EventState.FROZEN.value),
                        ":cycle": serializer.serialize(cycle),
                        ":updated": serializer.serialize(_utcnow()),
                    },
                }
            }
            for key in keys
        ]
        for attempt in range(TRANSACTION_ATTEMPTS):
            try:
                self.client.transact_write_items(TransactItems=transaction)
                return
            except self.client.exceptions.TransactionConflictException:
                if attempt == TRANSACTION_ATTEMPTS - 1:
                    raise
                time.sleep(random.uniform(0, min(0.4, 0.005 * (2**attempt))))
            except self.client.exceptions.TransactionCanceledException:
                current = self.get_event(event_id)
                if current["state"] == EventState.FROZEN.value:
                    return
                if attempt == TRANSACTION_ATTEMPTS - 1:
                    raise
                time.sleep(random.uniform(0, min(0.4, 0.005 * (2**attempt))))

    def freeze(self, event_id: str) -> EventSnapshot:
        """Close submissions and materialize an immutable snapshot, idempotently."""
        item = self._aggregate_event(self.ensure_event(event_id))
        if item["state"] == EventState.OPEN.value:
            if int(item["total_responses"]) < 1:
                raise CloudConflict("no hay respuestas para congelar")
            try:
                self._close_counter_shards(event_id, int(item["cycle"]))
                item = self._aggregate_event(self.get_event(event_id))
            except (
                self.client.exceptions.TransactionCanceledException,
                self.client.exceptions.TransactionConflictException,
            ) as exc:
                item = self._aggregate_event(self.get_event(event_id))
                if item["state"] != EventState.FROZEN.value:
                    raise CloudConflict("el evento cambió mientras se congelaba") from exc
        if item["state"] != EventState.FROZEN.value:
            raise CloudConflict(f"no se puede congelar desde {item['state']}")
        if item.get("snapshot"):
            return EventSnapshot.model_validate(item["snapshot"])
        snapshot = snapshot_from_event(item)
        self.events.update_item(
            Key={"event_id": event_id},
            UpdateExpression="SET #snapshot = :snapshot, updated_at = :updated",
            ConditionExpression="#state = :frozen AND #cycle = :cycle",
            ExpressionAttributeNames={
                "#state": "state",
                "#cycle": "cycle",
                "#snapshot": "snapshot",
            },
            ExpressionAttributeValues={
                ":snapshot": _ddb(snapshot.model_dump(mode="json")),
                ":updated": _utcnow(),
                ":frozen": EventState.FROZEN.value,
                ":cycle": item["cycle"],
            },
        )
        return snapshot

    def get_snapshot(self, event_id: str) -> EventSnapshot:
        """Read the active frozen snapshot."""
        item = self.get_event(event_id)
        if not item.get("snapshot"):
            raise KeyError("snapshot")
        return EventSnapshot.model_validate(item["snapshot"])

    def list_inventory(self) -> list[InventoryItem]:
        """Return the small, reproducible kitchen inventory."""
        items: list[dict[str, Any]] = []
        kwargs: dict[str, Any] = {}
        while True:
            result = self.inventory.scan(**kwargs)
            items.extend(_plain(result.get("Items", [])))
            if "LastEvaluatedKey" not in result:
                break
            kwargs["ExclusiveStartKey"] = result["LastEvaluatedKey"]
        return sorted(
            (InventoryItem.model_validate(item) for item in items),
            key=lambda item: item.ingredient_id,
        )

    def start_run(self, event_id: str, run_id: str) -> dict[str, Any]:
        """Transition FROZEN -> GENERATING and create the observable run record."""
        item = self.get_event(event_id)
        if item["state"] != EventState.FROZEN.value or not item.get("snapshot"):
            raise CloudConflict("primero debes congelar la encuesta")
        run = {
            "run_id": run_id,
            "cycle": item["cycle"],
            "status": "QUEUED",
            "started_at": _utcnow(),
            "steps": [],
        }
        try:
            self.events.update_item(
                Key={"event_id": event_id},
                UpdateExpression=(
                    "SET #state = :generating, #run = :run, updated_at = :updated "
                    "REMOVE validated_candidate"
                ),
                ConditionExpression="#state = :frozen AND #cycle = :cycle",
                ExpressionAttributeNames={
                    "#state": "state",
                    "#run": "run",
                    "#cycle": "cycle",
                },
                ExpressionAttributeValues={
                    ":frozen": EventState.FROZEN.value,
                    ":generating": EventState.GENERATING.value,
                    ":cycle": item["cycle"],
                    ":run": _ddb(run),
                    ":updated": _utcnow(),
                },
            )
        except self.client.exceptions.ConditionalCheckFailedException as exc:
            raise CloudConflict("ya existe una generación en curso") from exc
        return run

    def mark_run_running(self, event_id: str, run_id: str) -> None:
        """Mark an asynchronously invoked run as active."""
        self.events.update_item(
            Key={"event_id": event_id},
            UpdateExpression="SET #run.#status = :status, updated_at = :updated",
            ConditionExpression="#run.#run_id = :run_id",
            ExpressionAttributeNames={
                "#run": "run",
                "#status": "status",
                "#run_id": "run_id",
            },
            ExpressionAttributeValues={
                ":status": "RUNNING",
                ":run_id": run_id,
                ":updated": _utcnow(),
            },
        )

    def append_run_step(self, event_id: str, run_id: str, step: dict[str, Any]) -> None:
        """Append a small observable action, bounded to the Harness budget."""
        self.events.update_item(
            Key={"event_id": event_id},
            UpdateExpression=(
                "SET #run.#steps = list_append(if_not_exists(#run.#steps, :empty), :step), "
                "updated_at = :updated"
            ),
            ConditionExpression="#run.#run_id = :run_id",
            ExpressionAttributeNames={
                "#run": "run",
                "#steps": "steps",
                "#run_id": "run_id",
            },
            ExpressionAttributeValues={
                ":empty": [],
                ":step": [_ddb(step)],
                ":run_id": run_id,
                ":updated": _utcnow(),
            },
        )

    def fail_run(self, event_id: str, run_id: str, detail: str) -> None:
        """Return a failed mission to FROZEN so it can be retried."""
        self.events.update_item(
            Key={"event_id": event_id},
            UpdateExpression=(
                "SET #state = :frozen, #run.#status = :failed, "
                "#run.#error = :detail, #run.#finished = :finished, updated_at = :finished"
            ),
            ConditionExpression="#run.#run_id = :run_id",
            ExpressionAttributeNames={
                "#state": "state",
                "#run": "run",
                "#status": "status",
                "#error": "error",
                "#finished": "finished_at",
                "#run_id": "run_id",
            },
            ExpressionAttributeValues={
                ":frozen": EventState.FROZEN.value,
                ":failed": "FAILED",
                ":detail": detail[:1000],
                ":finished": _utcnow(),
                ":run_id": run_id,
            },
        )

    def complete_run(self, event_id: str, run_id: str) -> None:
        """Mark the run complete after the publish tool changed event state."""
        self.events.update_item(
            Key={"event_id": event_id},
            UpdateExpression=(
                "SET #run.#status = :complete, #run.#finished = :finished, updated_at = :finished"
            ),
            ConditionExpression="#run.#run_id = :run_id AND #state = :published",
            ExpressionAttributeNames={
                "#run": "run",
                "#status": "status",
                "#finished": "finished_at",
                "#run_id": "run_id",
                "#state": "state",
            },
            ExpressionAttributeValues={
                ":complete": "COMPLETED",
                ":finished": _utcnow(),
                ":run_id": run_id,
                ":published": EventState.PUBLISHED.value,
            },
        )

    def get_run(self, event_id: str, run_id: str) -> dict[str, Any]:
        """Return the active cycle's run when the identifier matches."""
        run = self.get_event(event_id).get("run")
        if not run or run.get("run_id") != run_id:
            raise KeyError(run_id)
        return run

    def stats(self, event_id: str) -> dict[str, Any]:
        """Return the public dashboard payload without individual responses."""
        item = self._aggregate_event(self.ensure_event(event_id))
        payload = {
            key: item.get(key)
            for key in (
                "event_id",
                "cycle",
                "state",
                "total_responses",
                "diet_counts",
                "lactose_intolerant_count",
                "gluten_free_count",
                "allergen_counts",
                "spice_counts",
                "cuisine_counts",
                "run",
            )
        }
        if int(item["total_responses"]) > 0:
            preview = snapshot_from_event(item)
            payload["derived_constraints"] = preview.derived_constraints.model_dump(mode="json")
            payload["top_preferred_ingredients"] = [
                count.model_dump(mode="json") for count in preview.top_preferred_ingredients
            ]
        payload["menu_available"] = bool(item.get("menu"))
        return payload
