"""Deterministic validation: the door every menu must pass before publishing.

Teaching concept: *probabilistic intelligence, deterministic control*.
"DO NOT violate allergies" in a prompt is a wish; the functions here are a
guarantee. The LLM proposes, this module disposes - in plain Python, with no
model call anywhere.

Layers (see docs/governance.md):

* :mod:`~chef_andino.validation.gates`     - shared hard constraints, used by
  BOTH the evaluator (as zero-score gates) and the validator (as blockers).
* :mod:`~chef_andino.validation.validator` - the full ordered check list.
"""

from chef_andino.validation.validator import VALIDATOR_VERSION, validate_menu

__all__ = ["VALIDATOR_VERSION", "validate_menu"]
