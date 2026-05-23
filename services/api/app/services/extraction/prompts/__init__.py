"""
LLM extraction prompt templates - versioned system and user prompts.

Available versions:
- v1: Original prompt (claude-sonnet-4-20250514, 3 examples, generic confidence)
- v2: Enhanced prompt (claude-opus-4-1, 10 examples, domain-aware, explicit confidence)
"""

from . import v1, v2

__all__ = ["v1", "v2"]
