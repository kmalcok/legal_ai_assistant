from __future__ import annotations

from functools import lru_cache
from pathlib import Path


def _src_root() -> Path:
    # .../src/utils/instruction_loader.py -> src/
    return Path(__file__).resolve().parents[1]


def _instructions_root() -> Path:
    return (_src_root() / "instructions").resolve()


def _safe_resolve(base: Path, rel_path: str) -> Path:
    """
    Resolve rel_path under base and prevent path traversal.
    """
    base_r = base.resolve()
    p = (base_r / rel_path).resolve()
    try:
        p.relative_to(base_r)
    except Exception as exc:
        raise ValueError(f"Path traversal blocked: {rel_path}") from exc
    return p


@lru_cache(maxsize=256)
def load_text(relative_path_from_instructions: str) -> str:
    """
    Load a text file from `src/instructions/` (cached).

    Example:
    - load_text("law_agentv2.md")
    - load_text("prompts/ictihat_summarize.md")
    """
    base = _instructions_root()
    p = _safe_resolve(base, relative_path_from_instructions)
    try:
        return p.read_text(encoding="utf-8")
    except Exception as exc:
        raise RuntimeError(f"Failed to read instructions file: {p}") from exc


def load_instruction_text(name: str) -> str:
    """
    Load a top-level instruction markdown file from `src/instructions/`.
    """
    return load_text(str(name))


def load_prompt_text(name: str) -> str:
    """
    Load a prompt template from `src/instructions/prompts/`.
    """
    return load_text(str(Path("prompts") / str(name)))

