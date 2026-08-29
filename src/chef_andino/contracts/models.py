"""The four data contracts, as Pydantic models.

1. :class:`SurveyResponse`  - one anonymous audience answer (enums only, no PII).
2. :class:`EventSnapshot`   - the frozen aggregate the agent reads.
3. :class:`InventoryItem`   - one ingredient in the kitchen (real state, not RAG).
4. :class:`Menu`            - the agent's final structured output.

Design notes for students:

* ``extra="forbid"`` everywhere: unknown fields are rejected, which is the
  JSON-Schema equivalent of ``additionalProperties: false``.
* :class:`SurveyResponse` has **no free-text field**. At a tech conference
  someone WILL type "ignore all previous instructions". Structured enums make
  prompt injection through the survey impossible by construction.
* ``consent`` is ``Literal[True]``: a response without explicit consent does
  not even parse.
* :class:`DerivedConstraints` is the pedagogical hinge: aggregation turns raw
  counts into machine-checkable rules that BOTH the evaluator's hard gates and
  the final validator consume - one definition, two enforcement points.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

# ---------------------------------------------------------------------------
# Shared vocabularies (enums)
# ---------------------------------------------------------------------------

Diet = Literal["none", "vegetarian", "vegan"]

Allergen = Literal["peanut", "tree_nuts", "shellfish", "fish", "egg", "soy"]

# Spice levels are ordered: mild < medium < hot.
SpiceLevel = Literal["mild", "medium", "hot"]
SPICE_ORDER: dict[str, int] = {"mild": 0, "medium": 1, "hot": 2}

CuisinePreference = Literal[
    "traditional_bolivian", "andean_fusion", "international", "no_preference"
]

PreferredIngredient = Literal[
    "quinoa", "potato", "corn", "aji_amarillo", "llama_meat",
    "trout", "chuno", "broad_beans", "amaranth", "peanut",
]

DietaryFlag = Literal["vegan", "vegetarian", "gluten_free", "lactose_free"]

IngredientCategory = Literal[
    "grain", "tuber", "vegetable", "fruit", "protein",
    "dairy", "spice", "herb", "legume", "other",
]

Course = Literal["breakfast", "starter", "main", "dessert"]


class StrictModel(BaseModel):
    """Base model: unknown fields are always an error."""

    model_config = ConfigDict(extra="forbid")


# ---------------------------------------------------------------------------
# 1. Survey response
# ---------------------------------------------------------------------------

class SurveyResponse(StrictModel):
    """One anonymous audience answer. Enums only - no names, no free text."""

    response_id: str = Field(description="Random UUID. Never tied to a person.")
    event_id: str
    submitted_at: datetime
    diet: Diet
    lactose_intolerant: bool
    gluten_free: bool
    allergies: list[Allergen] = Field(default_factory=list)
    spice_level: SpiceLevel = Field(description="Hottest level this person enjoys.")
    cuisine_preference: CuisinePreference
    preferred_ingredients: list[PreferredIngredient] = Field(
        default_factory=list, max_length=3
    )
    consent: Literal[True] = Field(
        description="Must be literally true: no consent, no parse."
    )


# ---------------------------------------------------------------------------
# 2. Event snapshot (the frozen aggregate)
# ---------------------------------------------------------------------------

class IngredientCount(StrictModel):
    """How many people named this ingredient as a favourite."""

    ingredient: PreferredIngredient
    count: int = Field(ge=1)


class DerivedConstraints(StrictModel):
    """Raw counts turned into machine-checkable rules.

    Derivation rules (see docs/data-contracts.md):

    * Any allergen declared by at least one person is excluded event-wide.
      Deliberately conservative - real catering would label per dish.
    * Any vegetarian or vegan respondent means one of the two lunch mains
      must be vegetarian - and because dinner has a SINGLE main, that main
      must be vegetarian too (the "one option must fit everyone" insight).
    * ``max_default_spice`` is the hottest level that at least 90% of
      respondents can enjoy.
    """

    must_exclude_allergens: list[Allergen]
    require_vegetarian_lunch_main: bool
    require_vegan_option_per_meal: bool
    require_gluten_free_option_per_meal: bool
    require_lactose_free_option_per_meal: bool
    max_default_spice: SpiceLevel


class EventSnapshot(StrictModel):
    """The frozen, anonymous aggregate that is the agent's ONLY view of people.

    Individual responses never reach the LLM: fewer tokens, no PII exposure,
    no injection surface, and a reproducible run (``snapshot_version``).
    """

    event_id: str
    snapshot_version: int = Field(ge=1)
    created_at: datetime
    total_responses: int = Field(ge=1)
    diet_counts: dict[Diet, int]
    lactose_intolerant_count: int = Field(ge=0)
    gluten_free_count: int = Field(ge=0)
    allergen_counts: dict[Allergen, int]
    spice_counts: dict[SpiceLevel, int]
    cuisine_counts: dict[CuisinePreference, int]
    top_preferred_ingredients: list[IngredientCount]
    derived_constraints: DerivedConstraints


# ---------------------------------------------------------------------------
# 3. Inventory item (real state -> tool, NOT RAG)
# ---------------------------------------------------------------------------

class InventoryItem(StrictModel):
    """One ingredient actually available in the kitchen.

    This is transactional state, so it lives behind a tool backed by a
    database (DynamoDB in the cloud) - not in the RAG corpus. Semantic
    knowledge goes to RAG; real state goes to tools.
    """

    ingredient_id: str = Field(pattern=r"^[a-z0-9_]+$")
    name: str
    category: IngredientCategory
    quantity: float = Field(ge=0)
    unit: Literal["kg", "l", "units"]
    allergens: list[Allergen] = Field(default_factory=list)
    dietary_flags: list[DietaryFlag] = Field(default_factory=list)
    is_bolivian: bool
    notes: str = ""


# ---------------------------------------------------------------------------
# 4. Menu (the agent's final structured output)
# ---------------------------------------------------------------------------

DISCLAIMER = (
    "Menú de demostración generado por IA (Chef Andino, AWS Community Day). "
    "No fue revisado por un nutricionista; el manejo de alérgenos es solo ilustrativo."
)

GenerationMode = Literal["live_agentcore", "fallback_last_good"]


class SourceRef(StrictModel):
    """Where a dish came from: the knowledge base, the web, or a template."""

    type: Literal["knowledge_base", "web", "template"]
    ref: str


class MenuItem(StrictModel):
    """One dish on the menu, with everything the validator needs to check it."""

    dish_id: str
    name: str
    description: str = Field(max_length=300)
    ingredients: list[str] = Field(min_length=1, description="inventory ingredient_ids")
    allergens: list[Allergen] = Field(default_factory=list)
    dietary_flags: list[DietaryFlag] = Field(default_factory=list)
    spice_level: SpiceLevel
    bolivian_origin: bool
    complexity: int = Field(ge=1, le=3, description="1 = trivial, 3 = demanding")
    sources: list[SourceRef] = Field(default_factory=list)


class Breakfast(StrictModel):
    """Breakfast is a simple buffet: 4 to 8 self-service items."""

    style: Literal["buffet"]
    items: list[MenuItem] = Field(min_length=4, max_length=8)


class Lunch(StrictModel):
    """Lunch: one starter, exactly two mains to choose from, one dessert."""

    starter: MenuItem
    mains: list[MenuItem] = Field(min_length=2, max_length=2)
    dessert: MenuItem


class Dinner(StrictModel):
    """Dinner: a SINGLE main (it must fit everyone) and one dessert."""

    main: MenuItem
    dessert: MenuItem


class Meals(StrictModel):
    """The three meals of the event day."""

    breakfast: Breakfast
    lunch: Lunch
    dinner: Dinner


class Coverage(StrictModel):
    """Computed (never LLM-claimed) facts about who the menu serves."""

    vegetarian_lunch_main: bool
    vegan_option_per_meal: bool
    gluten_free_option_per_meal: bool
    lactose_free_option_per_meal: bool
    preferred_ingredients_used: list[str]
    bolivian_ingredient_ratio: float = Field(ge=0, le=1)


class EvaluationResult(StrictModel):
    """Output of the ``evaluate_menu`` tool (the agent's own compass)."""

    total_score: float = Field(ge=0, le=1)
    breakdown: dict[str, float]
    hard_gates_passed: bool
    failed_gates: list[str] = Field(default_factory=list)


class Check(StrictModel):
    """One named validator rule and whether the menu passed it."""

    id: str
    passed: bool
    message: str


class ValidationReport(StrictModel):
    """Output of the deterministic validator (the door the menu must pass)."""

    passed: bool
    validator_version: str
    checks: list[Check]


class Menu(StrictModel):
    """The final structured output of a Chef Andino run.

    ``evaluation`` and ``validation`` are ``None`` on candidate menus and are
    attached by the evaluate and publish tools respectively - the agent cannot
    fabricate them in its own favour.
    """

    menu_id: str
    event_id: str
    cycle: int = Field(default=1, ge=1)
    run_id: str | None = None
    generation_mode: GenerationMode = "live_agentcore"
    snapshot_version: int = Field(ge=1)
    generated_at: datetime
    disclaimer: Literal[
        "Menú de demostración generado por IA (Chef Andino, AWS Community Day). "
        "No fue revisado por un nutricionista; el manejo de alérgenos es solo ilustrativo."
    ]
    meals: Meals
    coverage: Coverage | None = None
    evaluation: EvaluationResult | None = None
    validation: ValidationReport | None = None
    warnings: list[str] = Field(default_factory=list)
