from __future__ import annotations

import logging
import os
import shutil
import subprocess
import time
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, Dict, Iterable, List
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT, TA_RIGHT
from reportlab.lib.fonts import addMapping
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import HRFlowable, ListFlowable, ListItem, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from ..config import log_config


logger = logging.getLogger(__name__)


class PdfConversionError(RuntimeError):
    pass


def _libreoffice_logs_enabled() -> bool:
    try:
        return bool(log_config().libreoffice_logging_enabled)
    except Exception:
        return True


def _as_str(value: Any) -> str:
    return "" if value is None else str(value)


def _apply_events(events: List[Dict[str, Any]]) -> Dict[str, Any]:
    spec: Dict[str, Any] = {}
    blocks: List[Dict[str, Any]] = []
    inited = False
    for ev in events:
        if not isinstance(ev, dict):
            continue
        op = _as_str(ev.get("op")).strip().lower()
        if op == "init":
            meta = ev.get("meta") if isinstance(ev.get("meta"), dict) else {}
            spec = {
                "schemaVersion": "1.0",
                "meta": {"title": _as_str(meta.get("title")).strip()},
                "body": {"blocks": blocks},
            }
            inited = True
        elif op == "append" and inited and _as_str(ev.get("path")) == "body.blocks":
            value = ev.get("value")
            if isinstance(value, dict):
                blocks.append(value)
    return spec


def _normalize_docjson(spec_or_events: Any) -> Dict[str, Any]:
    if isinstance(spec_or_events, dict) and _as_str(spec_or_events.get("schemaVersion")).strip():
        return spec_or_events
    if isinstance(spec_or_events, list):
        return _apply_events([item for item in spec_or_events if isinstance(item, dict)])
    return {}


def _pick_font_variants() -> Dict[str, str]:
    windir = os.environ.get("WINDIR") or r"C:\Windows"
    fonts_dir = Path(windir) / "Fonts"
    families = [
        {
            "normal": "arial.ttf",
            "bold": "arialbd.ttf",
            "italic": "ariali.ttf",
            "boldItalic": "arialbi.ttf",
        },
        {
            "normal": "calibri.ttf",
            "bold": "calibrib.ttf",
            "italic": "calibrii.ttf",
            "boldItalic": "calibriz.ttf",
        },
        {
            "normal": "verdana.ttf",
            "bold": "verdanab.ttf",
            "italic": "verdanai.ttf",
            "boldItalic": "verdanaz.ttf",
        },
        {
            "normal": "times.ttf",
            "bold": "timesbd.ttf",
            "italic": "timesi.ttf",
            "boldItalic": "timesbi.ttf",
        },
    ]
    for family in families:
        normal_path = fonts_dir / family["normal"]
        if not normal_path.exists():
            continue
        out = {"normal": str(normal_path)}
        for key in ("bold", "italic", "boldItalic"):
            candidate = fonts_dir / family[key]
            out[key] = str(candidate if candidate.exists() else normal_path)
        return out
    return {}


def _ensure_font_family() -> Dict[str, str]:
    family_name = "YargucuPdfSans"
    normal_name = f"{family_name}-Regular"
    bold_name = f"{family_name}-Bold"
    italic_name = f"{family_name}-Italic"
    bold_italic_name = f"{family_name}-BoldItalic"
    if normal_name in pdfmetrics.getRegisteredFontNames():
        return {
            "regular": normal_name,
            "bold": bold_name,
            "italic": italic_name,
            "boldItalic": bold_italic_name,
        }

    variants = _pick_font_variants()
    if not variants:
        return {
            "regular": "Helvetica",
            "bold": "Helvetica-Bold",
            "italic": "Helvetica-Oblique",
            "boldItalic": "Helvetica-BoldOblique",
        }

    pdfmetrics.registerFont(TTFont(normal_name, variants["normal"]))
    pdfmetrics.registerFont(TTFont(bold_name, variants["bold"]))
    pdfmetrics.registerFont(TTFont(italic_name, variants["italic"]))
    pdfmetrics.registerFont(TTFont(bold_italic_name, variants["boldItalic"]))
    pdfmetrics.registerFontFamily(
        family_name,
        normal=normal_name,
        bold=bold_name,
        italic=italic_name,
        boldItalic=bold_italic_name,
    )
    addMapping(family_name, 0, 0, normal_name)
    addMapping(family_name, 1, 0, bold_name)
    addMapping(family_name, 0, 1, italic_name)
    addMapping(family_name, 1, 1, bold_italic_name)
    return {
        "regular": normal_name,
        "bold": bold_name,
        "italic": italic_name,
        "boldItalic": bold_italic_name,
    }


def _build_styles(font_names: Dict[str, str]) -> Dict[str, ParagraphStyle]:
    base_styles = getSampleStyleSheet()
    body = ParagraphStyle(
        "YargucuBody",
        parent=base_styles["BodyText"],
        fontName=font_names["regular"],
        fontSize=11,
        leading=16,
        spaceAfter=6,
        textColor=colors.black,
    )
    return {
        "title": ParagraphStyle("YargucuTitle", parent=body, fontName=font_names["bold"], fontSize=16, leading=21, alignment=TA_CENTER, spaceAfter=14),
        "h1": ParagraphStyle("YargucuH1", parent=body, fontName=font_names["bold"], fontSize=14, leading=18, spaceBefore=8, spaceAfter=8),
        "h2": ParagraphStyle("YargucuH2", parent=body, fontName=font_names["bold"], fontSize=12.5, leading=16, spaceBefore=6, spaceAfter=6),
        "h3": ParagraphStyle("YargucuH3", parent=body, fontName=font_names["bold"], fontSize=11.5, leading=15, spaceBefore=4, spaceAfter=4),
        "body": body,
        "meta": ParagraphStyle("YargucuMeta", parent=body, fontName=font_names["regular"], fontSize=9.5, leading=13, textColor=colors.HexColor("#555555")),
        "table": ParagraphStyle("YargucuTable", parent=body, fontName=font_names["regular"], fontSize=9.5, leading=12),
    }


def _alignment(value: str) -> int:
    key = _as_str(value).strip().lower()
    if key == "center":
        return TA_CENTER
    if key == "right":
        return TA_RIGHT
    if key == "justify":
        return TA_JUSTIFY
    return TA_LEFT


def _run_markup(runs: Iterable[Dict[str, Any]]) -> str:
    parts: List[str] = []
    for run in runs or []:
        if not isinstance(run, dict):
            continue
        text = escape(_as_str(run.get("text"))).replace("\n", "<br/>")
        if not text:
            continue
        if run.get("underline"):
            text = f"<u>{text}</u>"
        if run.get("italic"):
            text = f"<i>{text}</i>"
        if run.get("bold"):
            text = f"<b>{text}</b>"
        parts.append(text)
    return "".join(parts).strip()


def _paragraph_from_runs(block: Dict[str, Any], styles: Dict[str, ParagraphStyle]) -> Paragraph | None:
    runs = block.get("runs") if isinstance(block.get("runs"), list) else []
    markup = _run_markup(runs) if runs else escape(_as_str(block.get("text"))).replace("\n", "<br/>")
    if not markup.strip():
        return None
    style = ParagraphStyle(
        f"Paragraph-{id(block)}",
        parent=styles["body"],
        alignment=_alignment(_as_str(block.get("alignment"))),
    )
    return Paragraph(markup, style)


def _list_item_story(item: Dict[str, Any], ordered: bool, styles: Dict[str, ParagraphStyle], level: int) -> List[Any]:
    story: List[Any] = []
    text = escape(_as_str(item.get("text"))).replace("\n", "<br/>").strip()
    if text:
        story.append(Paragraph(text, styles["body"]))
    children = item.get("children") if isinstance(item.get("children"), list) else []
    if children:
        story.append(_list_flowable(children, ordered=ordered, styles=styles, level=level + 1))
    return story


def _list_flowable(items: List[Dict[str, Any]], *, ordered: bool, styles: Dict[str, ParagraphStyle], level: int = 0) -> ListFlowable:
    flow_items: List[ListItem] = []
    for item in items or []:
        if not isinstance(item, dict):
            continue
        story = _list_item_story(item, ordered, styles, level)
        if story:
            flow_items.append(ListItem(story))
    bullet_type = "1" if ordered else "bullet"
    return ListFlowable(
        flow_items,
        bulletType=bullet_type,
        start="1",
        leftIndent=18 + (level * 14),
        bulletFontName=styles["body"].fontName,
        bulletFontSize=styles["body"].fontSize,
    )


def _table_flowable(header: List[Any], rows: List[List[Any]], styles: Dict[str, ParagraphStyle]) -> Table | None:
    matrix: List[List[Any]] = []
    if header:
        matrix.append([Paragraph(f"<b>{escape(_as_str(cell))}</b>", styles["table"]) for cell in header])
    for row in rows or []:
        if not isinstance(row, list):
            continue
        matrix.append([Paragraph(escape(_as_str(cell)).replace("\n", "<br/>"), styles["table"]) for cell in row])
    if not matrix:
        return None

    max_cols = max(len(row) for row in matrix)
    normalized = []
    for row in matrix:
        padded = list(row) + [Paragraph("", styles["table"]) for _ in range(max_cols - len(row))]
        normalized.append(padded)

    table = Table(normalized, repeatRows=1 if header else 0, hAlign="LEFT")
    style_commands = [
        ("FONTNAME", (0, 0), (-1, -1), styles["table"].fontName),
        ("FONTSIZE", (0, 0), (-1, -1), styles["table"].fontSize),
        ("LEADING", (0, 0), (-1, -1), styles["table"].leading),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#C9CED6")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]
    if header:
        style_commands.extend(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#EEF2F7")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.black),
            ]
        )
    table.setStyle(TableStyle(style_commands))
    return table


def _build_story_from_docjson(spec_or_events: Any) -> List[Any]:
    spec = _normalize_docjson(spec_or_events)
    font_names = _ensure_font_family()
    styles = _build_styles(font_names)
    story: List[Any] = []

    meta = spec.get("meta") if isinstance(spec.get("meta"), dict) else {}
    title = _as_str(meta.get("title")).strip()
    if title:
        story.append(Paragraph(escape(title), styles["title"]))
        story.append(Spacer(1, 3 * mm))

    body = spec.get("body") if isinstance(spec.get("body"), dict) else {}
    blocks = body.get("blocks") if isinstance(body.get("blocks"), list) else []
    for block in blocks:
        if not isinstance(block, dict):
            continue
        kind = _as_str(block.get("type")).strip()
        if kind == "heading":
            level = max(1, min(int(block.get("level") or 1), 3))
            text = _as_str(block.get("text")).strip()
            if text:
                story.append(Paragraph(escape(text), styles[f"h{level}"]))
        elif kind == "paragraph":
            paragraph = _paragraph_from_runs(block, styles)
            if paragraph is not None:
                story.append(paragraph)
        elif kind == "list":
            items = block.get("items") if isinstance(block.get("items"), list) else []
            if items:
                story.append(_list_flowable(items, ordered=bool(block.get("ordered")), styles=styles))
                story.append(Spacer(1, 2 * mm))
        elif kind == "table":
            header = block.get("header") if isinstance(block.get("header"), list) else []
            rows = block.get("rows") if isinstance(block.get("rows"), list) else []
            table = _table_flowable(header, rows, styles)
            if table is not None:
                story.append(table)
                story.append(Spacer(1, 3 * mm))
        elif kind == "pageBreak":
            story.append(PageBreak())
        elif kind == "hr":
            story.append(HRFlowable(width="100%", thickness=0.7, color=colors.HexColor("#AAB4C3"), spaceBefore=4, spaceAfter=8))
        elif kind == "provenance":
            items = block.get("items") if isinstance(block.get("items"), list) else []
            rows = [[_as_str(item.get("label")), _as_str(item.get("value"))] for item in items if isinstance(item, dict)]
            table = _table_flowable(["Alan", "Değer"], rows, styles) if rows else None
            if table is not None:
                story.append(table)
                story.append(Spacer(1, 3 * mm))

    return story


def _build_story_from_text(text: str) -> List[Any]:
    font_names = _ensure_font_family()
    styles = _build_styles(font_names)
    story: List[Any] = []
    chunks = str(text or "").replace("\r\n", "\n").split("\n\n")
    for chunk in chunks:
        body = chunk.strip("\n")
        if not body.strip():
            continue
        story.append(Paragraph(escape(body).replace("\n", "<br/>"), styles["body"]))
    if not story:
        story.append(Paragraph("", styles["body"]))
    return story


def _build_pdf(story: List[Any], *, author: str = "Yargucu") -> bytes:
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
        title="Yargucu PDF Export",
        author=author,
    )
    doc.build(story)
    return buffer.getvalue()


def _pick_soffice_binary() -> str | None:
    env_path = str(os.environ.get("LIBREOFFICE_BIN") or "").strip()
    if env_path:
        return env_path
    for candidate in ("soffice", "libreoffice"):
        resolved = shutil.which(candidate)
        if resolved:
            return resolved
    return None


def convert_docx_bytes_to_pdf(
    docx_bytes: bytes,
    *,
    filename: str = "document.docx",
    timeout_seconds: int = 45,
) -> bytes:
    soffice_bin = _pick_soffice_binary()
    if not soffice_bin:
        if _libreoffice_logs_enabled():
            logger.warning("PDF conversion skipped: LibreOffice binary not available")
        raise PdfConversionError("libreoffice_not_available")

    safe_name = Path(str(filename or "document.docx")).name or "document.docx"
    if not safe_name.lower().endswith(".docx"):
        safe_name = f"{safe_name}.docx"

    started_at = time.perf_counter()
    if _libreoffice_logs_enabled():
        logger.info("PDF conversion start converter=libreoffice filename=%s binary=%s", safe_name, soffice_bin)

    with TemporaryDirectory(prefix="yargucu-pdf-") as tmpdir:
        tmp_path = Path(tmpdir)
        input_path = tmp_path / safe_name
        output_path = input_path.with_suffix(".pdf")
        input_path.write_bytes(docx_bytes or b"")

        cmd = [
            soffice_bin,
            "--headless",
            "--nologo",
            "--nodefault",
            "--nolockcheck",
            "--nofirststartwizard",
            "--convert-to",
            "pdf:writer_pdf_Export",
            "--outdir",
            str(tmp_path),
            str(input_path),
        ]
        try:
            proc = subprocess.run(
                cmd,
                check=False,
                capture_output=True,
                text=True,
                timeout=max(5, int(timeout_seconds)),
            )
        except subprocess.TimeoutExpired as exc:
            elapsed_ms = int((time.perf_counter() - started_at) * 1000)
            if _libreoffice_logs_enabled():
                logger.warning(
                    "PDF conversion failed converter=libreoffice filename=%s reason=timeout elapsed_ms=%s",
                    safe_name,
                    elapsed_ms,
                )
            raise PdfConversionError("libreoffice_timeout") from exc
        except Exception as exc:
            elapsed_ms = int((time.perf_counter() - started_at) * 1000)
            if _libreoffice_logs_enabled():
                logger.exception(
                    "PDF conversion failed converter=libreoffice filename=%s reason=exec_failed elapsed_ms=%s",
                    safe_name,
                    elapsed_ms,
                )
            raise PdfConversionError("libreoffice_exec_failed") from exc

        if proc.returncode != 0:
            detail = (proc.stderr or proc.stdout or "").strip()
            elapsed_ms = int((time.perf_counter() - started_at) * 1000)
            if _libreoffice_logs_enabled():
                logger.warning(
                    "PDF conversion failed converter=libreoffice filename=%s reason=nonzero_exit elapsed_ms=%s detail=%s",
                    safe_name,
                    elapsed_ms,
                    detail or "libreoffice_convert_failed",
                )
            raise PdfConversionError(detail or "libreoffice_convert_failed")
        if not output_path.exists():
            detail = (proc.stderr or proc.stdout or "").strip()
            elapsed_ms = int((time.perf_counter() - started_at) * 1000)
            if _libreoffice_logs_enabled():
                logger.warning(
                    "PDF conversion failed converter=libreoffice filename=%s reason=missing_output elapsed_ms=%s detail=%s",
                    safe_name,
                    elapsed_ms,
                    detail or "pdf_output_missing",
                )
            raise PdfConversionError(detail or "pdf_output_missing")
        pdf_bytes = output_path.read_bytes()
        elapsed_ms = int((time.perf_counter() - started_at) * 1000)
        if _libreoffice_logs_enabled():
            logger.info(
                "PDF conversion success converter=libreoffice filename=%s elapsed_ms=%s pdf_bytes=%s",
                safe_name,
                elapsed_ms,
                len(pdf_bytes),
            )
        return pdf_bytes


def render_pdf_from_docjson(spec_or_events: Any) -> bytes:
    return _build_pdf(_build_story_from_docjson(spec_or_events))


def render_pdf_from_text(text: str, *, prefer_monospace: bool = True) -> bytes:
    del prefer_monospace
    return _build_pdf(_build_story_from_text(text))

