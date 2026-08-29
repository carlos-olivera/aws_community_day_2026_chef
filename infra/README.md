# AWS infrastructure (CDK, Python)

Chef Andino is deployed as four CloudFormation stacks. The account comes from
the active AWS/CDK credentials and the default region is `us-east-1`; both can
be overridden with CDK context. All resources are tagged `Project=ChefAndino`
and `Environment=demo`.

## Resource map

| Stack | Managed resources |
|---|---|
| `ChefAndinoSurvey` | DynamoDB `Events`, `Responses` (48-hour TTL), and `Inventory`; presenter secret; private last-known-good S3 bucket; reproducible seed custom resource |
| `ChefAndinoKnowledge` | Private corpus S3 bucket, S3 Vectors index (Titan Text Embeddings v2, 1,024 dimensions, cosine), Bedrock Knowledge Base and data source |
| `ChefAndinoAgent` | Tool Lambda, authenticated MCP bridge, AgentCore Gateway, ACTIVE stateless and temporal Policy, Harness using `global.anthropic.claude-sonnet-4-6`, and async worker |
| `ChefAndinoFrontend` | HTTP API and Lambda, private S3 SPA, CloudFront/OAC, ACM certificate, Route 53 A/AAAA, and SPA-only rewrite function |

The Gateway exposes `get_event_snapshot`, `get_available_ingredients`,
`Retrieve`, `evaluate_menu`, `validate_menu`, and `publish_menu`. Because the
native Knowledge Base Gateway target does not support this S3 Vectors KB type,
`Retrieve` is implemented as a governed Lambda target that invokes Bedrock
Retrieve directly. The KB and vector index remain fully managed AWS resources.

Harness' native IAM Gateway adapter does not currently accept the
caller-managed header required by temporal Policy. The private-token MCP bridge
therefore preserves Harness' managed loop while signing each Gateway request
with its Lambda role and propagating the run ID as the Policy session. The
bridge token lives in Secrets Manager and is never included in the frontend.

## Lifecycle and safety

- A reset creates a new `cycle`; old responses are ignored and expire by TTL.
- Responses and one of 32 counter partitions are written transactionally and
  conditioned on that partition remaining `OPEN`.
- Freeze atomically closes the public event and all counter partitions before
  materializing the immutable snapshot.
- Generation is asynchronous and limited to one worker execution at a time.
- `publish_menu` is denied until the same candidate passed `validate_menu`
  within the temporal Policy session, and the Lambda revalidates it again.
- Buckets and tables use demo-friendly removal policies. Destruction is only
  performed by the explicit `make cloud-destroy` command.

## Deploy and verify

Run from the repository root:

```bash
make setup
make infra-test
make cloud-deploy
make cloud-smoke
make cloud-load
make cloud-reset
```

The site domain must be in an existing public Route 53 hosted zone and requires
all three context values. `make infra-test` uses non-deployable example values
when `CDK_ARGS` is omitted; `cloud-deploy` and `cloud-destroy` fail closed until
real values are supplied:

```bash
export CDK_ARGS='-c hostname=chef.example.com -c hostedZoneId=Z1234567890 -c hostedZoneName=example.com'
make infra-test CDK_ARGS="$CDK_ARGS"
make cloud-deploy CDK_ARGS="$CDK_ARGS"
```

Never commit account-specific output files, credentials, presenter
passphrases, or MCP bridge tokens. `.cloud/`, `.env`, CDK output, and local
runtime state are ignored by Git.

`cloud-deploy` stages Bedrock metadata sidecars, builds the Spanish SPA,
executes assertions against a fresh CDK synth, deploys all stacks, seeds
deterministic data, uploads the initial fallback,
starts KB ingestion, waits for `COMPLETE`, verifies retrieval, and runs the
HTTPS lifecycle smoke test. CloudWatch log retention is seven days.

The intentionally destructive command is separate:

```bash
make cloud-destroy
```
