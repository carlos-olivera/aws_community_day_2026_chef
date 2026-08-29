# Data contracts

Four schemas define every boundary in the system. The source of truth is
[`src/chef_andino/contracts/models.py`](../src/chef_andino/contracts/models.py)
(Pydantic); `make schemas` exports them as JSON Schema files under
[`src/chef_andino/contracts/schemas/`](../src/chef_andino/contracts/schemas/),
and a test fails if the two ever drift. The frontend keeps hand-written
mirrors in [`frontend/src/types.ts`](../frontend/src/types.ts).

## 1. SurveyResponse - one anonymous answer

| Field | Type | Notes |
|---|---|---|
| `response_id` | string (uuid) | random; never tied to a person |
| `event_id` | string | |
| `submitted_at` | datetime | assigned by the server, not the client |
| `diet` | `none \| vegetarian \| vegan` | |
| `lactose_intolerant` | bool | |
| `gluten_free` | bool | |
| `allergies` | list of `peanut \| tree_nuts \| shellfish \| fish \| egg \| soy` | categories only |
| `spice_level` | `mild \| medium \| hot` | the hottest this person enjoys |
| `cuisine_preference` | enum | traditional / fusion / international / none |
| `preferred_ingredients` | up to 3 from a fixed list | |
| `consent` | literally `true` | no consent, no parse |

Design decisions:

- **No free text, no PII.** Every field is a closed enum or boolean, and
  `additionalProperties: false` rejects anything extra. At a tech
  conference someone WILL submit "ignore all previous instructions" - here
  there is simply no field to put it in. Prompt injection through the
  survey is impossible by construction, not by filtering.
- **Consent is a type constraint** (`Literal[True]`), not a checkbox we
  hope somebody validates.

## 2. EventSnapshot - the frozen aggregate

Produced by [`build_snapshot`](../src/chef_andino/lifecycle/aggregate.py), a
pure function: N responses in, one snapshot out. Contains counts
(`diet_counts`, `allergen_counts`, `spice_counts`, ...), the top preferred
ingredients, and - the pedagogical hinge - `derived_constraints`:

| Constraint | Derivation rule |
|---|---|
| `must_exclude_allergens` | every allergen declared by >= 1 person |
| `require_vegetarian_lunch_main` | any vegetarian or vegan respondent |
| `require_vegan_option_per_meal` | any vegan respondent |
| `require_gluten_free_option_per_meal` | any gluten-free respondent |
| `require_lactose_free_option_per_meal` | any lactose-intolerant respondent |
| `max_default_spice` | hottest level >= 90% of respondents enjoy |

Aggregation converts raw counts into **machine-checkable rules** that both
the evaluator's hard gates and the final validator consume - one
definition, two enforcement points.

**A deliberate simplification:** one declared allergy bans the allergen
event-wide. Real catering would label allergens per dish and keep safe
options per guest; that would double the validator's complexity without
teaching anything new. The docs say so, the disclaimer says so, and
upgrading it is a good student exercise.

**Why individual responses never reach the LLM:** fewer tokens, zero PII
exposure, no injection surface, and reproducibility - the whole run cites
one `snapshot_version` and can be replayed against it.

## 3. InventoryItem - real state, not RAG

| Field | Type |
|---|---|
| `ingredient_id` | `^[a-z0-9_]+$` - the id dishes reference |
| `name`, `category`, `quantity`, `unit` | what the kitchen has |
| `allergens` | same enum as the survey |
| `dietary_flags` | `vegan / vegetarian / gluten_free / lactose_free` |
| `is_bolivian` | feeds the identity score |

The inventory is a database behind a tool (`get_available_ingredients`),
NOT a document in the RAG corpus. "RAG finds knowledge; it is not a
transactional database." Convention: dishes list main components only -
pantry basics (salt, oil) are not modelled.

## 4. Menu - the agent's structured output

```
menu_id, event_id, snapshot_version, generated_at, disclaimer (const),
meals:
  breakfast: style=buffet, items[4..8]
  lunch:     starter, mains[exactly 2], dessert
  dinner:    main, dessert          <- ONE main: must fit everyone
coverage    (computed, never claimed - see below)
evaluation  (attached by evaluate_menu)
validation  (attached by the publish gate)
warnings[]
```

Each `MenuItem` carries everything the validator needs: `ingredients`
(inventory ids), `allergens`, `dietary_flags`, `spice_level`,
`bolivian_origin`, `complexity` (1-3) and `sources` (knowledge_base / web /
template refs).

Two fields deserve attention:

- **`disclaimer` is a `const`.** A menu without the exact demo disclaimer
  does not even parse. The system never presents itself as a medical or
  food-safety authority.
- **`coverage`, `evaluation` and `validation` are attached by the system**,
  not proposed by the agent. Candidates carry `None`; the publish gate
  recomputes coverage and attaches the real validation report. The agent
  cannot grade its own homework.
