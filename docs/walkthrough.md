# Full local walkthrough - end to end

This guide walks the complete Chef Andino story on your machine, twice:
first in the terminal (Act 1-2), then through the web UI exactly as a
conference audience would experience it (Act 3). Then it shows you where
to look under the hood, and some experiments worth trying.

Everything runs offline. No AWS account, no cost.

## 0. One-time setup

```bash
cd aws_community_day_2026_chef

# Python side (skip if .venv already exists and `make test` passes)
make setup

# Frontend side (one time)
cd frontend && npm install && cd ..

# Activate the venv so `chef` is on your PATH for the rest of the guide
source .venv/bin/activate

# Sanity check: 66 tests in under a second
make test
```

---

## Act 1 - The mission, in the terminal

Start from a clean slate every time you rehearse:

```bash
chef reset --yes
```

**1. Seed the audience.** Loads 40 synthetic survey responses (the stand-in
for a live audience scanning a QR code) and creates the event in `OPEN`
state:

```bash
chef seed
```

**2. Look at the world the agent will see.** These are the live aggregates
the presenter dashboard shows - notice there are vegans, lactose-intolerant
people, and two declared peanut allergies:

```bash
chef stats
```

**3. Freeze the survey.** This is the snapshot pattern: `OPEN -> FROZEN`,
and aggregation writes an immutable snapshot v1. From here on, the agent
reads this version and nothing else:

```bash
chef freeze
```

**4. Run Chef Andino.** Watch the trace carefully - this is the heart of
the whole project:

```bash
chef run-agent
```

You will see, in order:

```
 v get_event_snapshot          <- observes the audience (aggregate only)
 v get_available_ingredients   <- what the kitchen really has
 v search_culinary_knowledge   <- x4: breakfast, starters, mains, desserts
 v research_web                <- optional inspiration (canned offline)
 POLICY DENY                   <- the agent tried to publish a menu with
 x validate_and_publish_menu      Sopa de Mani. Someone declared a peanut
                                  allergy. The validator failed it, the
                                  policy refused the action.
 v evaluate_menu               <- the repaired candidate scores ~0.7
 POLICY ALLOW
 v validate_and_publish_menu   <- published
```

The DENY is not a bug - it is injected on purpose (the first candidate
"overlooks" the allergy list, like a careless LLM would) so every run
demonstrates that **the model proposes, the system disposes**.

**5. The reveal:**

```bash
chef show-menu
```

Check what the constraints did to the menu: the dinner main is a single
dish, so with vegans in the audience it *must* be vegan+gluten-free+
lactose-free - and it is. That is constraint solving, not recipe
generation.

## Act 2 - The governance demo (30 seconds)

This one needs a **frozen, not yet published** event, so reset first:

```bash
chef reset --yes
chef seed
chef freeze
chef demo-governance
```

Two attempts are made with the *same, perfectly valid* menu:

1. publish while **skipping validation** -> `POLICY DENY` ("validation_passed
   is False"). The artifact was fine; the *process* was not. Policy checks
   process.
2. validate first, then publish -> `POLICY ALLOW`, menu published.

Both decisions land in the audit log it prints at the end.

> The model wanted to publish. The system did not let it.
> Autonomy without governance is just uncontrolled automation.

## Act 3 - The full web experience

Reset once more, and this time **do not freeze** - the audience is still
arriving:

```bash
chef reset --yes
chef seed          # optional: 40 synthetic guests so the dashboard isn't empty
```

Open **two terminals**:

```bash
# Terminal A - the backend (FastAPI on :8000)
source .venv/bin/activate
chef serve
```

```bash
# Terminal B - the frontend (Vite on :5173, proxies /api to :8000)
cd frontend
npm run dev
```

Now the story, in the browser:

1. **http://localhost:5173/** - the audience view (the QR target).
   Fill it a few times. Try being vegan with a peanut allergy. Note there
   is no free-text field anywhere: prompt injection through this form is
   impossible by construction, and the button stays disabled until you
   consent.
2. **http://localhost:5173/presenter** - the presenter view. Keep it open
   next to the survey tab and watch the counters move within ~2 seconds of
   each submission (the local and deployed demos both poll every two seconds). The
   constraint badges at the top ("no peanut", "vegan option required") are
   the derived constraints forming in real time.
3. Click **"Close survey (freeze)"** - state moves to FROZEN, the survey
   tab now gets "the survey is closed" if you try to submit again.
4. Click **"Chef Andino: begin"** - the agent runs server-side (watch
   Terminal A for the same trace as Act 1, DENY included) and the browser
   navigates to the menu when it publishes.
5. **http://localhost:5173/** - the audience route now reveals the full day's menu with
   dietary badges, verified coverage, the Bolivian-ingredient percentage
   and the disclaimer. The same URL the QR pointed at all along.

**Rehearsing with real phones:** run Vite with `npm run dev -- --host`,
find your machine's LAN IP, and point a QR generator at
`http://<your-ip>:5173/`. Phones on the same Wi-Fi can now feed the
agent - the closest local approximation of the conference moment.

## Under the hood - where to look

While (or after) any run:

```bash
# The whole database is one readable file - watch the state machine move
cat .localdata/db.json | head -50

# Every action the agent took, one JSON line per step
cat .localdata/runs/*/trace.jsonl

# Every policy decision ever made, with the computed context
cat .localdata/runs/*/audit.jsonl
```

The trace shows *observable actions* (tool, args, rationale, result,
budgets remaining) - never chain-of-thought. That is the same philosophy as
AgentCore Observability in the cloud phase.

## Experiments worth trying

- **A clean run:** `chef run-agent --no-flaw` - no DENY, straight to
  publish. Compare the traces.
- **Strangle the budget:** in
  [`src/chef_andino/config.py`](../src/chef_andino/config.py) set
  `max_iterations: int = 5`, reset+seed+freeze, run the agent, and watch
  the harness halt it mid-mission (`budget_exhausted`, event returns to
  FROZEN so you can retry). Put it back to 10 afterwards.
- **Break the menu on purpose:** delete `data/corpus/dishes/majadito_vegetal.md`
  and its `.meta.json`, run again - the planner has fewer universal mains
  to choose from. Then run `python scripts/check_corpus.py` and `make test`
  to see the safety nets (restore with `git checkout data/`).
- **Ban everything:** edit a few entries in
  [`scripts/generate_synthetic_responses.py`](../scripts/generate_synthetic_responses.py)
  to declare `egg` and `fish` allergies, regenerate
  (`python scripts/generate_synthetic_responses.py`), reset+seed+freeze,
  and watch the menu lose cunapes, silpancho and trout.
- **Real LLM as the brain** (optional, costs money):

  ```bash
  pip install -e ".[aws]"
  export AWS_REGION=us-east-1
  export BEDROCK_MODEL_ID=anthropic.claude-sonnet-5
  chef run-agent --planner bedrock
  ```

  Same tools, same validator, same policy - only the planner changed. If
  the model misbehaves, the gates catch it; that is the point.

## Troubleshooting

| Symptom | Cause / fix |
|---|---|
| `chef: command not found` | activate the venv (`source .venv/bin/activate`) or use `.venv/bin/chef` |
| Survey returns "the survey is closed" | event is FROZEN/PUBLISHED - `chef reset --yes && chef seed` |
| `demo-governance` raises IllegalTransition | it needs a FROZEN event that has not published - reset, seed, freeze first |
| Dashboard says "Waiting for the backend" | `chef serve` is not running on :8000 |
| Port 8000 already in use | `chef serve --port 8001` and change the proxy target in `frontend/vite.config.ts` |
| `run-agent` fails with "has no snapshot" | you skipped `chef freeze` |
| Vite proxy errors in Terminal B | start Terminal A (`chef serve`) first |

## The 5-minute rehearsal script (for the talk)

1. Before going on stage: `chef reset --yes && chef serve` + `npm run dev -- --host`, QR on screen pointing at `/`.
2. While talking: audience submits; `/presenter` projected, counters climbing.
3. "I think we know our guests well enough." -> **Close survey (freeze)**.
4. "Chef Andino: begin." -> click, switch the projector to Terminal A, narrate the trace - especially the DENY.
5. The audience route reveals the menu. "The QR that fed the agent now serves its result."
