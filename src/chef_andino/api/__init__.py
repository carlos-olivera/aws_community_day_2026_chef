"""The local HTTP API: what API Gateway + Lambda provide in the cloud phase.

Every endpoint is a thin wrapper over the same modules the CLI uses -
deliberately. Business logic that is transport-agnostic locally becomes
Lambda-ready for free.
"""
