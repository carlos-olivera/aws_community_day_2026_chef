# Chef Andino 🇧🇴 - an autonomous agent you can read end to end

Reference project for the talk **"Building Autonomous AI on AWS: From
Bedrock to Real-World Agent Systems"** (AWS Community Day, Santa Cruz de la
Sierra, Bolivia).

The story: a conference audience answers a 30-second anonymous dietary
survey from a QR code. When the presenter says *"Chef Andino: begin"*, an
autonomous agent designs the event's full-day menu - observing the
audience, consulting a Bolivian culinary knowledge base, checking the real
kitchen inventory, scoring candidates, and passing a deterministic
validator and a policy gate before it is allowed to publish.

> A chatbot answers. An agent receives a goal, observes the world, reasons,
> uses tools, verifies its own actions and produces a result.

The project has two equivalent execution paths. The local backbone runs
entirely offline, while the deployed AWS path uses managed AgentCore, Bedrock,
DynamoDB, Lambda, CloudFront, and S3 Vectors. Every cloud component still has a
small, readable local stand-in, so the system can be studied without an AWS
account and then mapped one-to-one
([docs/local-vs-cloud.md](docs/local-vs-cloud.md)).

## AWS educational demo

The event deployment is [https://chef.carlosolivera.me](https://chef.carlosolivera.me)
in `us-east-1`. Availability is not guaranteed after the event. The audience
experience and result share that URL; the protected presenter console is
[https://chef.carlosolivera.me/presenter](https://chef.carlosolivera.me/presenter).

Retrieve the presenter passphrase without putting it in source code or shell
history:

```bash
aws secretsmanager get-secret-value \
  --secret-id "$(jq -r '.ChefAndinoSurvey.PresenterSecretArn' .cloud/outputs.json)" \
  --query SecretString --output text | jq -r .passphrase
```

Operational commands are idempotent:

```bash
make cloud-deploy  # test, build, deploy, seed, ingest KB, and smoke test
make infra-test    # fresh CDK synth + infrastructure assertions
make cloud-smoke   # OPEN -> FROZEN -> GENERATING -> PUBLISHED + fallback
make cloud-load    # 1,300 anonymous responses and latency assertions
make cloud-reset   # new empty OPEN cycle; leaves the URL unchanged
make cloud-destroy # explicit only; never run by cloud-deploy
```

The current implementation uses polling every two seconds, a private S3 SPA
behind CloudFront/OAC, API Gateway HTTP API, DynamoDB transactions with 32
counter partitions, AgentCore Harness/Gateway/temporal Policy, and a Bedrock
Knowledge Base backed by S3 Vectors. See [infra/README.md](infra/README.md) for
the resource map and deployment notes.

## Quickstart (5 commands, zero AWS)

```bash
make setup          # venv + editable install
make demo           # seed -> stats -> freeze -> run agent -> show menu
```

or step by step:

```bash
make setup
.venv/bin/chef seed                # load 40 synthetic survey responses
.venv/bin/chef stats               # what the live dashboard shows
.venv/bin/chef freeze              # close the survey -> immutable snapshot v1
.venv/bin/chef run-agent           # Chef Andino runs (watch the DENY -> repair -> ALLOW)
.venv/bin/chef show-menu           # the published menu
.venv/bin/chef demo-governance     # 30-second policy demo (fresh event: chef reset --yes && chef seed && chef freeze)
make test                          # application and end-to-end tests
```

Every run writes an action trace and a policy audit log to
`.localdata/runs/<run_id>/` - open them, they are the observability story.

### Web UI (optional)

```bash
.venv/bin/chef serve                  # FastAPI on :8000
cd frontend && npm ci && npm run dev  # Vite on :5173
```

Then open `/` for the audience experience and `/presenter` for the protected
presenter controls. The audience route changes from survey to status to menu
as the event lifecycle advances.

### Real LLM mode (optional, costs money)

```bash
pip install -e ".[aws]"
chef run-agent --planner bedrock   # requires AWS credentials + model access
```

Nothing else changes - same loop, same tools, same gates. See
[docs/agent-loop.md](docs/agent-loop.md).

## What you'll learn (concept -> code)

| Concept | Where it lives |
|---|---|
| Agent = Model + Goal + Context + Tools + Loop | [`agent/runner.py`](src/chef_andino/agent/runner.py) |
| The LLM is swappable (mock <-> Bedrock) | [`planner/`](src/chef_andino/planner) |
| Tools are the API of the agent's world | [`tools/`](src/chef_andino/tools) |
| Semantic knowledge -> RAG; real state -> tools | [`tools/knowledge.py`](src/chef_andino/tools/knowledge.py) vs [`tools/inventory.py`](src/chef_andino/tools/inventory.py) |
| The snapshot pattern (frozen, versioned world) | [`lifecycle/`](src/chef_andino/lifecycle) |
| Probabilistic intelligence, deterministic control | [`validation/`](src/chef_andino/validation) |
| Autonomy needs governance (default-deny policy) | [`policy/`](src/chef_andino/policy) |
| Bounded autonomy (budgets in the harness) | [`agent/budgets.py`](src/chef_andino/agent/budgets.py) |
| Observable actions, not chain-of-thought | [`agent/trace.py`](src/chef_andino/agent/trace.py) |
| Structured output as a contract | [`contracts/models.py`](src/chef_andino/contracts/models.py) |
| Prompt injection prevented by construction | [`api/app.py`](src/chef_andino/api/app.py) (enums only, no free text) |

## Repository map

```
src/chef_andino/     the Python package (agent, tools, validation, policy, API, CLI)
frontend/            React/Vite SPA: survey, presenter dashboard, menu reveal
data/                culinary corpus, kitchen inventory, synthetic responses
infra/               deployed AWS CDK application (Python)
docs/                architecture, contracts, agent loop, governance, ADRs
tests/               unit / api / e2e - the whole story is asserted
scripts/             corpus linter + data (re)generators
.localdata/          runtime state (gitignored): db.json + run traces
```

Start with [docs/architecture.md](docs/architecture.md); every module's
docstring names the teaching concept it embodies. For a guided end-to-end
tour (CLI + web UI + experiments), follow
[docs/walkthrough.md](docs/walkthrough.md).

## Reuse and contribute

The offline path needs only Python 3.12+. Cloud deployment also needs Node.js
20.19+ (or 22.12+), AWS credentials, a bootstrapped CDK environment, Bedrock model access,
and incurs AWS charges. A public Route 53 domain is required so CloudFront can
enforce the TLS policy used by the demo. Pass all three values together (they
are deployment configuration, never credentials):

```bash
make infra-test CDK_ARGS='-c hostname=chef.example.com -c hostedZoneId=Z1234567890 -c hostedZoneName=example.com'
make cloud-deploy CDK_ARGS='-c hostname=chef.example.com -c hostedZoneId=Z1234567890 -c hostedZoneName=example.com'
```

Read [CONTRIBUTING.md](CONTRIBUTING.md) before opening a pull request and
[SECURITY.md](SECURITY.md) before reporting a vulnerability. The project is
licensed under [Apache-2.0](LICENSE).

## The architecture in one line

```
Audience QR -> survey (structured, anonymous) -> frozen snapshot vN
    -> bounded agent loop (6 tools) -> deterministic validator
    -> policy gate (default DENY) -> published menu -> same QR
```

Cloud implementation: API Gateway + Lambda + DynamoDB for the data plane;
Amazon Bedrock **AgentCore** Harness, Gateway and temporal Policy plus Bedrock
Knowledge Bases/S3 Vectors for the intelligence plane. AppSync Events, Browser,
Code Interpreter and WAF are intentionally outside this educational version.

## Disclaimer

This is an educational demonstration. Menus are AI-generated examples; the
conservative allergen handling here is illustrative and is **not** a food
safety mechanism - real catering requires professional review.
