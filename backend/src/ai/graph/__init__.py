"""
LangGraph multi-agent runtime for the Yargucu law assistant.

This package replaces the openai-agents SDK runtime for the *main* law agent.
It wires two agents that share a single graph state:

- ``main_agent``     : the supervisor / general law assistant
- ``petition_agent`` : the dilekçe (petition) specialist the supervisor hands off to

The student agent and the ictihat sub-agents intentionally still run on the
openai-agents SDK; only the main law agent has been migrated here.
"""

from __future__ import annotations

from .state import AgentState

__all__ = ["AgentState"]
