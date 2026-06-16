# Instructions (Agent Prompts)

This folder contains **source-of-truth** agent instruction texts as plain **Markdown** files.

Why:
- Easier to review/edit prompts without touching Python code
- Cleaner diffs and prompt iteration
- Allows multiple agents to share prompts consistently

Files:
- `law_agentv2.md`: Main Turkish law assistant system instructions used by `LawAssistantAgent`.
- `law_agent.md`: Legacy version kept for reference.
- `ictihat_search_agent.md`: Instructions for the `IctihatSearchAgent` (sub-agent) that performs iterative ictihat search.
- `prompts/`: Other LLM prompt templates used by tool wrappers and internal services.

