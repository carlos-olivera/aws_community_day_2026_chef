"""Policy: deterministic authorization for agent actions.

Teaching concept: *autonomy without governance is just uncontrolled
automation*. The model never decides whether a rule applies - enforcement
happens outside the agent. Locally this is a tiny default-deny engine over
``policies.yaml``; in the cloud phase the same rules become Cedar policies
evaluated by Amazon Bedrock AgentCore Policy at the Gateway.
"""

from chef_andino.policy.engine import (
    LocalPolicyEngine,
    PolicyDecision,
    PolicyRequest,
)

__all__ = ["LocalPolicyEngine", "PolicyDecision", "PolicyRequest"]
