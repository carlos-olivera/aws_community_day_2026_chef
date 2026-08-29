# Contributing to Chef Andino

Thank you for helping improve this educational reference project. Keep changes
small, readable, and tied to a teaching outcome.

## Local development

Requirements: Python 3.12+, Node.js 20.19+ (or 22.12+), npm, and GNU Make.

```bash
make setup
make lint
make test
python scripts/check_corpus.py
make infra-test
```

The offline demo must remain usable without AWS credentials. Use `npm ci`, not
`npm install`, when validating the committed frontend lockfile. Cloud tests may
incur cost; do not deploy as part of a pull request unless the change requires
it and you control the target AWS account.

## Pull requests

- Explain the behavior and educational value of the change.
- Add or update tests and documentation with the code.
- Keep generated output, local state, credentials, account IDs, secrets, and
  presenter passphrases out of commits.
- Run the validation commands above and report any check you could not run.
- Do not include participant names, contact data, or free-form survey content.

By submitting a contribution, you agree that it is licensed under the
repository's Apache License 2.0.
