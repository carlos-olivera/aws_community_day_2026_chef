# Architecture

Chef Andino is one system with two deployments: a **local backbone** that
runs entirely offline (this repo, today) and a **cloud target** on AWS
(next phase). Both share the same four planes:

```
Experience  ->  Data  ->  Intelligence  ->  Governance
```

## The story in one paragraph

The audience scans a QR code and answers a 30-second structured survey.
Responses accumulate in storage while a dashboard shows live aggregates.
The presenter **freezes** the event: aggregation turns N individual answers
into ONE anonymous, versioned snapshot. Then the agent runs a single
mission - design the day's menu - using six tools, inside a bounded loop.
A deterministic validator and a policy engine stand between the agent and
the publish action. The published menu appears on the same QR code that fed
the agent.

## Local backbone (what runs today)

```mermaid
flowchart TD
    A[Survey SPA<br/>React/Vite] -->|POST /responses| B[FastAPI<br/>chef_andino.api]
    B --> C[(LocalJsonStore<br/>.localdata/db.json)]
    D[Dashboard SPA] -->|GET /stats poll 2s| B
    B -->|freeze| E[build_snapshot<br/>pure function]
    E --> C
    B -->|generate| F[AgentRunner<br/>bounded loop]
    F <--> G[Planner<br/>Mock or Bedrock]
    F --> H[ToolRegistry<br/>6 tools]
    H --> C
    H --> I[data/corpus<br/>keyword search]
    H --> J[evaluate_menu<br/>plain Python]
    H --> K[validate_and_publish]
    K --> L[Deterministic validator]
    K --> M[Policy engine<br/>policies.yaml]
    K -->|ALLOW| C
    F --> N[trace.jsonl + audit.jsonl]
    O[Menu SPA] -->|GET /menu| B
```

## Event lifecycle

```mermaid
stateDiagram-v2
    [*] --> OPEN : create
    OPEN --> FROZEN : freeze (snapshot vN written)
    FROZEN --> GENERATING : agent run starts
    GENERATING --> PUBLISHED : validated menu published
    GENERATING --> FROZEN : run failed (retry later)
    PUBLISHED --> [*]
```

`PUBLISHED` is terminal. Snapshots are immutable: re-freezing writes a new
version, never overwrites. The whole agent run reads a single
`snapshot_version` - that is what makes runs reproducible.

## One agent mission, step by step

```mermaid
sequenceDiagram
    participant R as AgentRunner
    participant P as Planner
    participant T as Tools
    participant V as Validator
    participant Po as Policy

    R->>P: next_action()
    P->>T: get_event_snapshot
    P->>T: get_available_ingredients
    P->>T: search_culinary_knowledge (x4 courses)
    P->>T: research_web (optional)
    P->>T: validate_and_publish_menu (flawed candidate)
    T->>V: validate -> FAILED (allergens)
    T->>Po: publish_menu? -> DENY
    Note over P: reads failed checks, repairs menu
    P->>T: evaluate_menu -> score 0.74
    P->>T: validate_and_publish_menu
    T->>V: validate -> PASSED
    T->>Po: publish_menu? -> ALLOW
    R->>R: event -> PUBLISHED
```

Every arrow to Tools is one **iteration** charged against the budget
(`max_iterations=10`). The DENY -> repair -> ALLOW cycle is injected on
purpose in every mock run (see [agent-loop.md](agent-loop.md)) so the
governance story is always visible.

## Deployed cloud architecture

```mermaid
flowchart TD
    QR[Audience QR] --> SPA[SPA on S3/CloudFront]
    SPA --> APIGW[API Gateway HTTP API]
    APIGW --> L1[Lambda handlers<br/>same chef_andino modules]
    L1 --> DDB[(DynamoDB<br/>responses + events)]
    SPA -->|poll every 2 seconds| DASH[Live dashboard]
    DASH --> APIGW
    ADMIN[Presenter + bearer secret] -->|freeze / generate| APIGW
    L1 --> HARNESS[AgentCore Harness<br/>managed agent loop]
    HARNESS --> PROXY[Authenticated MCP bridge<br/>policy session propagation]
    PROXY --> GW[AgentCore Gateway<br/>tools as MCP]
    GW --> POL[AgentCore Policy<br/>Cedar]
    GW --> KB[Retrieve Lambda<br/>Knowledge Base + S3 Vectors]
    GW --> TOOLS[Tool Lambdas<br/>snapshot / inventory / evaluate / validate / publish]
    HARNESS --> OBS[CloudWatch logs<br/>7-day retention]
```

The mapping between the two diagrams is one-to-one and is tabulated in
[local-vs-cloud.md](local-vs-cloud.md). The point of the backbone is that
**nothing conceptual changes** when you swap the adapters: the loop, the
contracts, the validator and the policy rules survive the move. Browser,
Web Search, Code Interpreter, AppSync Events and WAF are intentionally out
of scope for this first educational deployment.

## Design rules the code enforces

1. **One LLM mission per event, not per participant.** Aggregation is
   deterministic software; intelligence starts only when a decision cannot
   be expressed as a reasonable set of if/else.
2. **Semantic knowledge -> RAG; real state -> tools.** The corpus knows what
   tarwi is; only the inventory tool knows there are 14 kg of it.
3. **Probabilistic intelligence, deterministic control.** The model
   proposes; validator + policy dispose. Its mistakes do not become actions.
4. **Bounded autonomy.** Budgets live in the runner, not the prompt.
5. **Internet is inspiration, not authority.** `research_web` can fail;
   the mission cannot depend on it.
6. **Observable actions, not chain-of-thought.** The trace shows what the
   agent did - which is also what you can actually audit in production.
