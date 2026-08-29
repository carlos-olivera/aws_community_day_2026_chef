"""The agent harness: a bounded, observable loop around the planner.

Teaching concepts:

* *Bounded autonomy* - budgets are enforced HERE, in deterministic code,
  not requested politely in the prompt.
* *Observability* - every action, result and policy decision is written to
  a JSONL trace, because "when a chatbot fails, someone reads a bad answer;
  when an agent fails, it may execute a bad action".

Locally this loop is ~60 lines of Python; in the cloud phase Amazon Bedrock
AgentCore Harness plays this role as a managed service.
"""

from chef_andino.agent.budgets import BudgetExceeded, BudgetTracker
from chef_andino.agent.runner import AgentRunner, RunResult

__all__ = ["AgentRunner", "BudgetExceeded", "BudgetTracker", "RunResult"]
