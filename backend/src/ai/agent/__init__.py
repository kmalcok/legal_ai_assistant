"""
Agent package.

Do NOT import concrete agents at module import time.
This avoids circular imports when tools/agents import each other.
"""

__all__ = ["LawAssistantAgent"]


def __getattr__(name: str):
    if name == "LawAssistantAgent":
        # Lazy import to avoid circular imports.
        from .law_agent import LawAssistantAgent as _LawAssistantAgent

        return _LawAssistantAgent
    raise AttributeError(name)


