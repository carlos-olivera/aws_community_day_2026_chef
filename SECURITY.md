# Security policy

## Supported version

Security fixes are applied to the current `main` branch. This is an educational
demo, not a production food-safety or identity system.

## Report a vulnerability

Please use GitHub's private vulnerability reporting or a private Security
Advisory for this repository. Do not open a public issue containing exploit
details, credentials, passphrases, tokens, account identifiers, participant
data, or screenshots that expose them.

Include the affected component, reproduction steps, impact, and any suggested
mitigation. You should receive an acknowledgment within seven days. Avoid
testing against the event deployment or accessing data that is not your own.

## Deployment boundary

- Survey answers use enumerated fields and are intended to be anonymous.
- Presenter and MCP bridge secrets belong in AWS Secrets Manager and must never
  be placed in frontend code, logs, shell history, or repository files.
- `.cloud/`, `.env`, local runtime state, and synthesized CDK assets are not
  source artifacts and must remain untracked.
- Each public deployment owner is responsible for AWS IAM review, cost limits,
  logging, retention, regional availability, and professional food-safety
  review before using generated menus.
