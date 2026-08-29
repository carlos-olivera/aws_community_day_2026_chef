"""build_snapshot: turn N individual responses into ONE anonymous aggregate.

Teaching concepts:

* *An event must not trigger one LLM invocation per participant.* Hundreds of
  form submissions are aggregated deterministically (plain Python, no AI) and
  the agent receives a single snapshot.
* This is a **pure function**: responses in, snapshot out, no I/O. In the
  cloud phase it becomes the body of the freeze Lambda, unchanged.
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone

from chef_andino.contracts.models import (
    SPICE_ORDER,
    DerivedConstraints,
    EventSnapshot,
    IngredientCount,
    SpiceLevel,
    SurveyResponse,
)

# A dish's default spice must suit at least this share of the audience.
SPICE_ACCEPTANCE_THRESHOLD = 0.9

TOP_INGREDIENTS = 5


def _max_default_spice(responses: list[SurveyResponse]) -> SpiceLevel:
    """Hottest level that at least 90% of respondents can enjoy.

    Someone whose ``spice_level`` is "medium" enjoys mild and medium dishes;
    a dish at level L is acceptable to everyone whose tolerance is >= L.
    """
    total = len(responses)
    best: SpiceLevel = "mild"
    for level in ("medium", "hot"):
        accepting = sum(
            1 for r in responses if SPICE_ORDER[r.spice_level] >= SPICE_ORDER[level]
        )
        if accepting / total >= SPICE_ACCEPTANCE_THRESHOLD:
            best = level  # type: ignore[assignment]
    return best


def build_snapshot(
    event_id: str,
    responses: list[SurveyResponse],
    version: int,
    now: datetime | None = None,
) -> EventSnapshot:
    """Aggregate responses into an immutable, versioned snapshot."""
    if not responses:
        raise ValueError("cannot build a snapshot from zero responses")

    diet_counts = Counter(r.diet for r in responses)
    allergen_counts = Counter(a for r in responses for a in r.allergies)
    spice_counts = Counter(r.spice_level for r in responses)
    cuisine_counts = Counter(r.cuisine_preference for r in responses)
    ingredient_counts = Counter(i for r in responses for i in r.preferred_ingredients)

    any_vegetarian_or_vegan = diet_counts["vegetarian"] + diet_counts["vegan"] > 0
    constraints = DerivedConstraints(
        # Conservative on purpose: one declared allergy bans the allergen
        # event-wide. Real catering would label per dish instead.
        must_exclude_allergens=sorted(allergen_counts),
        require_vegetarian_lunch_main=any_vegetarian_or_vegan,
        require_vegan_option_per_meal=diet_counts["vegan"] > 0,
        require_gluten_free_option_per_meal=any(r.gluten_free for r in responses),
        require_lactose_free_option_per_meal=any(r.lactose_intolerant for r in responses),
        max_default_spice=_max_default_spice(responses),
    )

    return EventSnapshot(
        event_id=event_id,
        snapshot_version=version,
        created_at=now or datetime.now(timezone.utc),
        total_responses=len(responses),
        diet_counts={d: diet_counts.get(d, 0) for d in ("none", "vegetarian", "vegan")},
        lactose_intolerant_count=sum(1 for r in responses if r.lactose_intolerant),
        gluten_free_count=sum(1 for r in responses if r.gluten_free),
        allergen_counts=dict(sorted(allergen_counts.items())),
        spice_counts={s: spice_counts.get(s, 0) for s in ("mild", "medium", "hot")},
        cuisine_counts=dict(sorted(cuisine_counts.items())),
        top_preferred_ingredients=[
            IngredientCount(ingredient=i, count=c)
            for i, c in ingredient_counts.most_common(TOP_INGREDIENTS)
        ],
        derived_constraints=constraints,
    )
