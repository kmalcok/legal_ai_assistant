from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple


def _as_str(x: Any) -> str:
    return "" if x is None else str(x)


def _tr_upper(s: str) -> str:
    """
    Turkish-aware uppercasing.
    Avoids Python's default i->I mapping for Turkish headings.
    """
    s = s or ""
    table = {
        "i": "İ",
        "ı": "I",
        "ş": "Ş",
        "ğ": "Ğ",
        "ü": "Ü",
        "ö": "Ö",
        "ç": "Ç",
        "â": "Â",
        "î": "Î",
        "û": "Û",
    }
    return "".join(table.get(ch, ch.upper()) for ch in s)


def _get_blocks(spec: Dict[str, Any]) -> List[Dict[str, Any]]:
    body = spec.get("body") if isinstance(spec.get("body"), dict) else {}
    blocks = body.get("blocks") if isinstance(body.get("blocks"), list) else []
    return [b for b in blocks if isinstance(b, dict)]


def _apply_events(events: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Copy of the event application logic used by docjson_renderer:
    - init creates base spec
    - append to body.blocks adds blocks
    """
    spec: Dict[str, Any] = {}
    blocks: List[Dict[str, Any]] = []
    inited = False
    for ev in events:
        if not isinstance(ev, dict):
            continue
        op = _as_str(ev.get("op")).strip().lower()
        if op == "init":
            meta = ev.get("meta") if isinstance(ev.get("meta"), dict) else {}
            title = _as_str(meta.get("title")).strip()
            spec = {
                "schemaVersion": "1.0",
                "meta": {"title": title},
                "body": {"blocks": blocks},
            }
            inited = True
        elif op == "append":
            if not inited:
                continue
            path = _as_str(ev.get("path"))
            if path != "body.blocks":
                continue
            val = ev.get("value")
            if isinstance(val, dict):
                blocks.append(val)
    return spec


def _table_to_lines(header: Optional[List[Any]], rows: List[List[Any]]) -> List[str]:
    # Normalize cells
    grid: List[List[str]] = []
    if header:
        grid.append([_as_str(c).strip() for c in header])
    for r in rows:
        if isinstance(r, list):
            grid.append([_as_str(c).strip() for c in r])
    if not grid:
        return []

    ncols = max(len(r) for r in grid)
    for r in grid:
        if len(r) < ncols:
            r.extend([""] * (ncols - len(r)))

    widths = [0] * ncols
    for r in grid:
        for i, c in enumerate(r):
            widths[i] = max(widths[i], len(c))
    widths = [max(1, w) for w in widths]

    def fmt_row(r: List[str]) -> str:
        parts = [r[i].ljust(widths[i]) for i in range(ncols)]
        return " | ".join(parts).rstrip()

    def sep(ch: str = "-") -> str:
        parts = [ch * widths[i] for i in range(ncols)]
        return "-+-".join(parts)

    out: List[str] = []
    if header:
        out.append(fmt_row(grid[0]))
        out.append(sep("-"))
        for r in grid[1:]:
            out.append(fmt_row(r))
    else:
        for r in grid:
            out.append(fmt_row(r))
    return out


def docjson_to_text(spec_or_events: Any) -> Tuple[str, Dict[str, Any]]:
    """
    Convert DOC-JSON v1 payload (full spec OR append-event list) into readable plain text.
    Returns (text, info) where info includes simple flags (e.g. has_table).
    """
    spec: Dict[str, Any]
    if isinstance(spec_or_events, dict) and _as_str(spec_or_events.get("schemaVersion")).strip():
        spec = spec_or_events
    elif isinstance(spec_or_events, list):
        spec = _apply_events([e for e in spec_or_events if isinstance(e, dict)])
    else:
        spec = {}

    blocks = _get_blocks(spec) if isinstance(spec, dict) else []
    lines: List[str] = []
    has_table = False

    title = _as_str((spec.get("meta") or {}).get("title") if isinstance(spec.get("meta"), dict) else "").strip()
    if title:
        lines.append(title)
        lines.append("")

    for b in blocks:
        t = _as_str(b.get("type")).strip()
        if t == "heading":
            lvl = int(b.get("level") or 1)
            txt = _as_str(b.get("text")).strip()
            if txt:
                if lvl <= 1:
                    lines.append(_tr_upper(txt))
                else:
                    lines.append(txt)
                lines.append("")
        elif t == "paragraph":
            runs = b.get("runs")
            if isinstance(runs, list):
                txt = "".join(_as_str(r.get("text")) for r in runs if isinstance(r, dict))
            else:
                txt = _as_str(b.get("text"))
            txt = txt.strip()
            if txt:
                lines.append(txt)
                lines.append("")
        elif t == "list":
            ordered = bool(b.get("ordered") or False)
            items = b.get("items") if isinstance(b.get("items"), list) else []

            def walk(item: Dict[str, Any], prefix: str, depth: int) -> None:
                text = _as_str(item.get("text")).strip()
                if text:
                    indent = "  " * max(0, depth)
                    lines.append(f"{indent}{prefix}{text}")
                children = item.get("children")
                if isinstance(children, list):
                    for j, ch in enumerate(children, start=1):
                        if isinstance(ch, dict):
                            p2 = f"{j}) " if ordered else "- "
                            walk(ch, p2, depth + 1)

            for i, it in enumerate(items, start=1):
                if not isinstance(it, dict):
                    continue
                prefix = f"{i}) " if ordered else "- "
                walk(it, prefix, 0)
            if items:
                lines.append("")
        elif t == "table":
            header = b.get("header") if isinstance(b.get("header"), list) else None
            rows = b.get("rows") if isinstance(b.get("rows"), list) else []
            row_lists = [r for r in rows if isinstance(r, list)]
            tbl_lines = _table_to_lines(header, row_lists)
            if tbl_lines:
                has_table = True
                lines.extend(tbl_lines)
                lines.append("")
        elif t == "hr":
            lines.append("―" * 32)
            lines.append("")
        elif t == "provenance":
            items = b.get("items") if isinstance(b.get("items"), list) else []
            rows = []
            for it in items:
                if not isinstance(it, dict):
                    continue
                lab = _as_str(it.get("label")).strip()
                val = _as_str(it.get("value")).strip()
                if lab or val:
                    rows.append([lab, val])
            tbl_lines = _table_to_lines(["Alan", "Değer"], rows) if rows else []
            if tbl_lines:
                has_table = True
                lines.extend(tbl_lines)
                lines.append("")
        else:
            continue

    # trim trailing blanks
    while lines and not lines[-1].strip():
        lines.pop()

    text = "\n".join(lines).strip() + "\n"
    return text, {"has_table": has_table}

