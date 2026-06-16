from __future__ import annotations

import hashlib
import os
import re
from pathlib import Path
from typing import Iterable, List


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def safe_filename(name: str) -> str:
    name = (name or "").strip()
    if not name:
        return "file"
    # Keep extension but sanitize the rest
    name = name.replace("\\", "/").split("/")[-1]
    name = re.sub(r"[^a-zA-Z0-9._ -]+", "_", name).strip()
    name = re.sub(r"\s+", " ", name).strip()
    return name[:200] if len(name) > 200 else name


def ensure_dir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)


def normalize_text(s: str) -> str:
    s = (s or "").replace("\x00", " ")
    s = re.sub(r"[ \t]+", " ", s)
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s.strip()


def split_into_pseudopages(text: str, *, max_chars: int = 5000) -> List[str]:
    """
    Deterministic pseudo-pagination by character budget.
    Keeps paragraphs when possible.
    """
    text = normalize_text(text)
    if not text:
        return [""]

    max_chars = max(500, int(max_chars))
    paras = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]

    pages: list[str] = []
    buf: list[str] = []
    cur = 0

    def flush():
        nonlocal buf, cur
        if buf:
            pages.append("\n\n".join(buf).strip())
        buf = []
        cur = 0

    for p in paras:
        if not buf:
            buf.append(p)
            cur = len(p)
            continue
        if cur + 2 + len(p) <= max_chars:
            buf.append(p)
            cur += 2 + len(p)
            continue
        flush()
        buf.append(p)
        cur = len(p)

    flush()
    return pages or [text]


def first_sentence(s: str, *, max_chars: int = 240) -> str:
    s = normalize_text(s)
    if not s:
        return ""
    # crude but works: split by sentence enders
    m = re.split(r"(?<=[.!?])\s+", s, maxsplit=1)
    out = (m[0] if m else s).strip()
    if len(out) > max_chars:
        out = out[: max_chars - 1] + "…"
    return out


def shorten(s: str, max_chars: int) -> str:
    s = s or ""
    if max_chars <= 0:
        return ""
    if len(s) <= max_chars:
        return s
    return s[: max_chars - 1] + "…"


def guess_ext(filename: str) -> str:
    return os.path.splitext((filename or "").lower())[1].lstrip(".")


def join_lines(lines: Iterable[str], *, max_chars: int) -> str:
    out_parts: list[str] = []
    used = 0
    for ln in lines:
        ln = ln or ""
        if not ln:
            continue
        if used + len(ln) + 1 > max_chars:
            break
        out_parts.append(ln)
        used += len(ln) + 1
    return "\n".join(out_parts).strip()


