# Local vs cloud: the component map

The backbone runs offline with small, readable stand-ins for every AWS
service in the target architecture. Each row below is a **port**: the
interface stays, the adapter changes. The deployed IaC for the right-hand
column lives in [`infra/`](../infra/README.md).

| Concern | Local backbone (this repo) | Cloud phase (AWS) |
|---|---|---|
| Survey + menu UI | Vite dev server | Private S3 + CloudFront/OAC |
| HTTP API | FastAPI (`chef serve`) | API Gateway HTTP API + Lambda |
| Storage | `LocalJsonStore` - one JSON file | DynamoDB on-demand, response TTL and cycle-based reset |
| Realtime dashboard | 2-second polling | 2-second polling through CloudFront `/api/*` |
| Presenter auth | none (documented as local-only) | Shared bearer secret in Secrets Manager and browser `sessionStorage` |
| Agent loop | `AgentRunner` (~60 lines) | Amazon Bedrock **AgentCore Harness** (managed loop) |
| The brain | `MockPlanner` (scripted) / `BedrockPlanner` (Converse API from the laptop) | a foundation model on Amazon Bedrock |
| Tool plumbing | `ToolRegistry` (in-process) | **AgentCore Gateway** - Lambdas/APIs exposed as MCP tools |
| Culinary knowledge (RAG) | `LocalCorpusSearch` - keyword + metadata filter over `data/corpus/` | Bedrock **Knowledge Bases + S3 Vectors**, filterable metadata from the `.meta.json` files |
| Inventory (real state) | JSON seed file behind a tool | DynamoDB behind a Lambda tool - **not** RAG, on purpose |
| Web research | `CannedWebResearch` (offline, honest about it) | Outside the first cloud version |
| Menu scoring | plain Python (`evaluate_menu`) | The same deterministic evaluator in a Lambda tool |
| Hard-rule validation | pure-Python validator | Separate `validate_menu` and `publish_menu` Lambda tools |
| Action authorization | `LocalPolicyEngine` + `policies.yaml` (Cedar-shaped, default-deny) | **AgentCore Policy** - Cedar, enforced at the Gateway |
| Observability | `trace.jsonl` + `audit.jsonl` + rich console | **AgentCore Observability** (CloudWatch, OTEL traces) |
| Agent evaluation | pytest scenario suite | **AgentCore Evaluations** (on-demand / batch / online) |
| Structured output | Pydantic `Menu` contract | Pydantic/JSON Schema validation at every write boundary |

## Reading the table

Three patterns repeat across every row - and they are the transferable
architecture lessons:

**1. Semantic knowledge -> RAG. Real state -> tools/APIs.**
The corpus explains what tarwi is; only the inventory knows there are 14 kg
of it. In enterprise terms: manuals -> RAG, stock -> ERP API;
documentation -> RAG, balance -> banking API.

**2. The managed service replaces the harness, not the thinking.**
AgentCore Harness, Gateway and Policy replace `runner.py`, `base.py` and
`engine.py` - the boring, critical plumbing. Your contracts, your validator
rules and your policy semantics move unchanged. Building the local version
first means you understand exactly what the managed service does for you.

**3. Mature architecture is knowing what NOT to use.**
No Step Functions, no EventBridge, no SQS, no microservices fleet - and no
AgentCore Memory: this mission is deliberately ephemeral (one snapshot in,
one menu out), and storing individual dietary data in a long-term memory
service would be exactly the wrong instinct. Mentioning a service and
declining it is an architecture decision too.

## Region note (cloud phase)

The deployed demo uses `us-east-1`, selected explicitly in the CDK context
and deployment commands.
