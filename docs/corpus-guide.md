# The culinary corpus

`data/corpus/` is Chef Andino's knowledge base: small, curated, and
structured to grow. It currently holds ~30 documents in three folders:

```
data/corpus/
  dishes/        20 dishes  (the planner builds menus from these)
  ingredients/    8 ingredient profiles
  techniques/     3 event-cooking techniques
```

Quality over quantity is the point: a RAG corpus of 50 excellent documents
beats 5,000 mediocre ones, and retrieval behaviour is identical to teach.

## Document format

Every document is a pair:

```
dishes/sopa_de_quinua.md          the prose (title + 2 short paragraphs)
dishes/sopa_de_quinua.meta.json   filterable metadata
```

This mirrors Amazon Bedrock Knowledge Bases, where each source document can
carry a metadata sidecar used for **filtered retrieval** - restricting by
attributes, not just semantic similarity. The local search engine
([`tools/knowledge.py`](../src/chef_andino/tools/knowledge.py)) applies the
same idea: metadata filters first, keyword ranking second.

### Dish metadata (all fields required)

```json
{
  "type": "dish",
  "name": "Sopa de Quinua",
  "course": "starter",              // breakfast | starter | main | dessert
  "tags": ["soup", "quinoa", "bolivian"],
  "ingredients": ["quinoa", "potato", "carrot", "onion"],
  "allergens": [],
  "dietary_flags": ["vegan", "vegetarian", "gluten_free", "lactose_free"],
  "spice_level": "mild",
  "bolivian_origin": true,
  "complexity": 1                   // 1 trivial .. 3 demanding
}
```

Rules (enforced by `python scripts/check_corpus.py`):

- every `.md` has a `.meta.json` and vice versa;
- every id in `ingredients` exists in `data/inventory.seed.json` (dishes
  list *main components* only - salt and oil are not modelled);
- implied flags are explicit: a `vegan` dish must also list `vegetarian`
  and `lactose_free`. Retrieval filters match literally; nothing infers.

Ingredient and technique documents need only `type`, `name`, `tags`
(plus `ingredient_id` for ingredients).

## How search works locally

`search_culinary_knowledge(query, filters)`:

1. **Filter**: keep documents whose metadata satisfies every filter key
   (list values match on overlap).
2. **Rank**: score by keyword overlap between the query and the document's
   title + tags + first paragraph; ties break alphabetically (determinism
   matters for the mock planner and the tests).
3. Return the top 5 with `doc_id`, `title`, `snippet`, `metadata`, `score`.

Deliberately naive - a few dozen readable lines. The cloud phase swaps in
Knowledge Bases + S3 Vectors (documents -> chunks -> embeddings -> vector
index -> semantic retrieval) behind the same port, so students can diff the
two retrieval engines while everything around them stays identical.

## Adding a dish (checklist)

1. Write `dishes/<slug>.md`: a `# Title`, one paragraph of what it is, one
   paragraph of why/how it works for large events.
2. Write `dishes/<slug>.meta.json` with all fields above.
3. Any new ingredient? Add it to `data/inventory.seed.json` first.
4. `python scripts/check_corpus.py` - fix what it flags.
5. `make test` - menu assembly and search tests still pass.

Mind the balance the mock planner relies on: several universal mains
(vegan + gluten-free + lactose-free) must always survive the constraint
filter, and the breakfast pool needs at least four acceptable items.
