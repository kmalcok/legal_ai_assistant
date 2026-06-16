from __future__ import annotations

import io
import zipfile
from math import isfinite
from typing import Any, Dict, List, Optional


def _safe_cdata(s: str) -> str:
    """
    Ensure text is safe to embed inside a single CDATA section.
    """
    s = s or ""
    # CDATA cannot contain "]]>".
    return s.replace("]]>", "]]]]><![CDATA[>")


def _tr_upper(s: str) -> str:
    """
    Turkish-aware uppercasing for common petition headings.
    Python's default .upper() maps "i" -> "I" (English-style), but Turkish expects "İ".
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


def _as_list(x: Any) -> List[str]:
    if x is None:
        return []
    if isinstance(x, list):
        return [str(i) for i in x if str(i or "").strip()]
    if isinstance(x, str):
        return [x] if x.strip() else []
    return [str(x)]


def _cm_to_udf_points(cm: float) -> float:
    """
    UYAP UDF pageFormat margin unit appears to be typographic points.
    Example: 1.5 cm ~= 42.525 pt.
    """
    return float(cm) * 72.0 / 2.54


def _fmt_udf_float(x: float) -> str:
    """
    Match UYAP-ish float formatting (many decimals).
    """
    try:
        x = float(x)
    except Exception:
        x = 0.0
    if not isfinite(x):
        x = 0.0
    s = f"{x:.15f}"
    return s.rstrip("0").rstrip(".") if "." in s else s


def _center_line(s: str, *, width: int = 86) -> str:
    """
    Best-effort centering for UDF viewers.
    UYAP editors commonly use proportional fonts, so this is approximate.
    """
    s = (s or "").rstrip()
    if not s:
        return ""
    width = max(20, int(width))
    pad = (width - len(s)) // 2
    if pad <= 0:
        return s
    # Many viewers trim regular leading spaces; NBSP is less likely to be stripped.
    return ("\u00A0" * pad) + s


def _render_plaintext_lines(output: Dict[str, Any]) -> tuple[list[str], list[str]]:
    """
    Render lines + per-line style tags.
    style tag values: "default" | "red"
    """
    meta = output.get("meta") if isinstance(output, dict) else {}
    if not isinstance(meta, dict):
        meta = {}

    lines: list[str] = []
    styles: list[str] = []

    def add_line(s: str, *, style: str = "default") -> None:
        lines.append(str(s or ""))
        styles.append(style if style in {"default", "red"} else "default")

    def add_blank() -> None:
        add_line("", style="default")

    court = str(meta.get("court") or "").strip()
    if court:
        # Title is centered in DOCX; approximate it in UDF by left-padding.
        add_line(_center_line(_tr_upper(court)), style="default")
        add_blank()

    # Header blocks
    blocks = output.get("header_blocks") if isinstance(output, dict) else None
    if not isinstance(blocks, list):
        blocks = []

    urgent: list[str] = []
    rest: list[tuple[str, str, str]] = []  # (label,value,styleTag)
    for b in blocks:
        if not isinstance(b, dict):
            continue
        label = str(b.get("label") or "")
        value = str(b.get("value") or "")
        st = b.get("style") if isinstance(b, dict) else None
        is_red = isinstance(st, dict) and str(st.get("color") or "").strip().lower() == "red"
        style_tag = "red" if is_red else "default"
        if not label.strip() and value.strip():
            urgent.append(value.strip())
        elif label.strip() or value.strip():
            rest.append((label.strip(), value.strip(), style_tag))

    for v in urgent:
        add_line(v, style="default")
    if urgent:
        add_blank()

    # Try to mimic DOCX header block alignment: "LABEL\t: VALUE"
    for label, value, style_tag in rest:
        if label and value:
            add_line(f"{label}\t: {value}", style=style_tag)
        elif value:
            add_line(value, style=style_tag)
    if rest:
        add_blank()

    # Sections
    sections = output.get("sections") if isinstance(output, dict) else None
    if isinstance(sections, list):
        for s in sections:
            if not isinstance(s, dict):
                continue
            title = str(s.get("title") or "").strip()
            if title:
                add_blank()
                add_line(_tr_upper(title), style="default")
                add_blank()
            blks = s.get("blocks")
            if not isinstance(blks, list):
                blks = []
            for bl in blks:
                if not isinstance(bl, dict):
                    continue
                kind = str(bl.get("kind") or "").strip()
                text = bl.get("text")
                if kind == "numbered":
                    add_blank()
                    items = _as_list(text)
                    for i, item in enumerate(items, start=1):
                        add_line(f"{i}. {item}", style="default")
                elif kind == "bullets":
                    add_blank()
                    items = _as_list(text)
                    for item in items:
                        add_line(f"- {item}", style="default")
                elif kind == "block_quote":
                    q = str(text or "").strip()
                    if q:
                        # Render quotes as indented text (no markdown ">" prefix).
                        # Some UDF viewers show raw ">" characters which looks messy.
                        add_blank()
                        for ln in q.splitlines():
                            ln = ln.strip()
                            if ln:
                                add_line("      " + ln, style="default")
                        add_blank()
                else:
                    p = str(text or "").strip()
                    if p:
                        # Simple first-line indent like in DOCX renderer.
                        add_line("    " + p, style="default")
            add_blank()

    # Signature
    sig = output.get("signature") if isinstance(output, dict) else None
    if isinstance(sig, dict):
        place_date = str(sig.get("place_date_line") or "").strip()
        phrase = str(sig.get("phrase") or "").strip()
        name_line = str(sig.get("name_line") or "").strip()
        if place_date or phrase or name_line:
            if place_date:
                add_line(place_date, style="default")
            if phrase:
                add_line(phrase, style="default")
            if name_line:
                add_line(name_line, style="default")
            add_blank()

    # Attachments list (textual)
    atts = output.get("attachments") if isinstance(output, dict) else None
    if isinstance(atts, list) and [a for a in atts if str(a or "").strip()]:
        add_line("EKLER", style="default")
        for i, a in enumerate(atts, start=1):
            a = str(a or "").strip()
            if a:
                add_line(f"{i}. {a}", style="default")
        add_blank()

    # Trim trailing blank lines
    while lines and not lines[-1].strip():
        lines.pop()
        styles.pop()

    return lines, styles


def render_plaintext(output: Dict[str, Any]) -> str:
    """
    Render a petition output JSON (petitions/output.schema.json) into a readable plain text.

    This is intentionally conservative: it aims for readability and robust export,
    not perfect fidelity with UYAP Editor rendering.
    """
    lines, _styles = _render_plaintext_lines(output)
    # IMPORTANT: do not .strip() here, because we intentionally use leading
    # indentation (spaces / NBSP) for layout in UDF viewers.
    return "\n".join(lines).rstrip() + "\n"


def render_udf_bytes(
    *,
    output: Dict[str, Any],
    include_documentproperties: bool = False,
    document_properties: Optional[Dict[str, str]] = None,
) -> bytes:
    """
    Create a UDF (UYAP Doküman Formatı) ZIP package.

    Contents:
    - content.xml (UYAP Editor "template" XML)
    - documentproperties.xml (optional; off by default)

    The `content.xml` structure is modeled after common UYAP Editor outputs:
    `<template format_id="1.8">` with `<content><![CDATA[...]]></content>`,
    `<elements>` with paragraph offsets/lengths, and basic `<styles>`.
    """
    lines, line_styles = _render_plaintext_lines(output)
    text = "\n".join(lines).rstrip() + "\n"

    # Pick margins from petition style (cm) if present, else match our DOCX renderer defaults.
    meta = output.get("meta") if isinstance(output, dict) else {}
    style = meta.get("style") if isinstance(meta, dict) and isinstance(meta.get("style"), dict) else {}
    margins_cm = style.get("margins_cm") if isinstance(style, dict) and isinstance(style.get("margins_cm"), dict) else {}
    # DOCX defaults in docx_renderer.py:
    # top=2.5, bottom=2.5, left=3.75, right=2.5
    try:
        top_cm = float(margins_cm.get("top", 2.5) or 2.5)
        bottom_cm = float(margins_cm.get("bottom", 2.5) or 2.5)
        left_cm = float(margins_cm.get("left", 3.75) or 3.75)
        right_cm = float(margins_cm.get("right", 2.5) or 2.5)
    except Exception:
        top_cm, bottom_cm, left_cm, right_cm = 2.5, 2.5, 3.75, 2.5
    left_pt = _cm_to_udf_points(left_cm)
    right_pt = _cm_to_udf_points(right_cm)
    top_pt = _cm_to_udf_points(top_cm)
    bottom_pt = _cm_to_udf_points(bottom_cm)

    # Build paragraph offset/length map using line breaks.
    # The sample UDF counts the newline character as part of the paragraph length.
    # We enforce a trailing newline in render_plaintext(), so splitlines(True) is stable.
    segs = text.replace("\r\n", "\n").splitlines(True)
    if not segs:
        segs = [""]
    # Align style tags with splitlines(True) output:
    # - line_styles corresponds to logical lines without trailing '\n'
    # - splitlines(True) includes the '\n' in each segment except possibly the last,
    #   but we always ensure trailing newline above.
    if len(line_styles) != len(segs):
        # Best-effort: pad/truncate to avoid index errors.
        if len(line_styles) < len(segs):
            line_styles = list(line_styles) + ["default"] * (len(segs) - len(line_styles))
        else:
            line_styles = list(line_styles[: len(segs)])
    start = 0
    para_specs: list[tuple[int, int]] = []
    for seg in segs:
        ln = len(seg)
        para_specs.append((start, ln))
        start += ln

    # UYAP-like content.xml (template format_id="1.8")
    # Keep formatting compact; consumers typically ignore whitespace.
    elements_parts: list[str] = []
    for idx, (off, ln) in enumerate(para_specs):
        if ln <= 0:
            continue
        st = (line_styles[idx] or "default").strip().lower() if idx < len(line_styles) else "default"
        if st == "red":
            # Best-effort style application: set resolver on paragraph and content.
            # If one is ignored, the other may still apply.
            elements_parts.append(
                f'<paragraph resolver="hvl-red"><content resolver="hvl-red" startOffset="{int(off)}" length="{int(ln)}" /></paragraph>'
            )
        else:
            elements_parts.append(f'<paragraph><content startOffset="{int(off)}" length="{int(ln)}" /></paragraph>')
    elements_xml = "".join(elements_parts)
    if not elements_xml:
        elements_xml = '<paragraph><content startOffset="0" length="0" /></paragraph>'

    # Match common UYAP Editor formatting (note the trailing space after '?>').
    content_xml_str = (
        '<?xml version="1.0" encoding="UTF-8" ?> \n\n'
        '<template format_id="1.8" >\n'
        f"<content><![CDATA[{_safe_cdata(text)}]]></content>"
        '<properties><pageFormat mediaSizeName="1" leftMargin="'
        + _fmt_udf_float(left_pt)
        + '" rightMargin="'
        + _fmt_udf_float(right_pt)
        + '" topMargin="'
        + _fmt_udf_float(top_pt)
        + '" bottomMargin="'
        + _fmt_udf_float(bottom_pt)
        + '" paperOrientation="1" headerFOffset="20.0" '
        'footerFOffset="20.0" /></properties>\n'
        '<elements resolver="hvl-default" >\n'
        f"{elements_xml}\n"
        "</elements>\n"
        '<styles><style name="default" description="Geçerli" family="Dialog" size="12" '
        'bold="false" italic="false" '
        'FONT_ATTRIBUTE_KEY="javax.swing.plaf.FontUIResource[family=Dialog,name=Dialog,style=plain,size=12]" '
        'foreground="-13421773" />'
        '<style name="hvl-default" family="Times New Roman" size="12" description="Gövde" />'
        '<style name="hvl-red" family="Times New Roman" size="12" description="Kırmızı" foreground="-65536" />'
        "</styles>\n"
        "</template>\n"
    )
    content_xml = content_xml_str.encode("utf-8")

    props_xml: bytes | None = None
    if include_documentproperties:
        props = document_properties or {}
        # keep it tiny + XML-safe (simple tags with escaped text)
        def _xml_escape(v: str) -> str:
            v = v or ""
            return (
                v.replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;")
                .replace('"', "&quot;")
                .replace("'", "&apos;")
            )

        props_lines = [
            '<?xml version="1.0" encoding="UTF-8"?>',
            "<documentProperties>",
        ]
        for k, v in props.items():
            kk = "".join(ch for ch in str(k) if ch.isalnum() or ch in {"_", "-"})
            if not kk:
                continue
            props_lines.append(f"  <{kk}>{_xml_escape(str(v))}</{kk}>")
        props_lines.append("</documentProperties>")
        props_xml = ("\n".join(props_lines) + "\n").encode("utf-8")

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("content.xml", content_xml)
        if props_xml is not None:
            zf.writestr("documentproperties.xml", props_xml)
    return buf.getvalue()


def render_udf_from_text(text: str) -> bytes:
    """
    Convenience helper for non-petition exports (e.g., ephemeral DOCX -> UDF).
    """
    # Minimal shape expected by render_plaintext; we keep it as a single paragraph.
    output = {
        "meta": {"document_type": "", "court": ""},
        "header_blocks": [],
        "sections": [{"title": "", "blocks": [{"kind": "paragraph", "text": str(text or "")}]}],
        "signature": {},
    }
    return render_udf_bytes(output=output, include_documentproperties=False)


def render_udf_from_text_with_style(text: str, *, font_family: str = "Times New Roman") -> bytes:
    """
    Like render_udf_from_text but allows overriding the default style font family.
    Useful for monospace exports so tables align better.
    """
    text = str(text or "")
    # Build a minimal output object, but embed the font family via a small patch:
    # we don't have per-paragraph styles in this simplified UDF template,
    # so we set the overall style family.
    b = render_udf_from_text(text)
    try:
        import zipfile
        import io

        with zipfile.ZipFile(io.BytesIO(b), "r") as z:
            content = z.read("content.xml").decode("utf-8", errors="replace")
        content2 = content.replace('family="Times New Roman"', f'family="{font_family}"')
        out = io.BytesIO()
        with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED) as z2:
            z2.writestr("content.xml", content2.encode("utf-8"))
        return out.getvalue()
    except Exception:
        return b

