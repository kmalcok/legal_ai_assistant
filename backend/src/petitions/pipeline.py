from __future__ import annotations

from copy import deepcopy
import json
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

from jsonschema import Draft202012Validator

from .docx_renderer import render_docx_bytes
from .udf_renderer import render_udf_bytes


class PetitionPipelineError(Exception):
    pass


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")

def _fold_tr(s: str) -> str:
    """
    Lowercase + cheap Turkish diacritic folding for robust substring checks.
    (Used only for heuristic cleanup in rendered sections.)
    """
    s = (s or "").strip().lower()
    # Normalize and remove combining marks (e.g. "İ".lower() -> "i\u0307")
    s = unicodedata.normalize("NFKD", s)
    s = "".join(ch for ch in s if unicodedata.category(ch) != "Mn")
    table = str.maketrans(
        {
            "ç": "c",
            "ğ": "g",
            "ı": "i",
            "ö": "o",
            "ş": "s",
            "ü": "u",
            "â": "a",
            "î": "i",
            "û": "u",
        }
    )
    return s.translate(table)


def _is_netice_title(title: Any) -> bool:
    f = _fold_tr(str(title or "").strip())
    if not f:
        return False
    if "netice ve talep" in f:
        return True
    # tolerate encoding/normalization artifacts around Turkish dotted i
    if re.search(r"net.?ce\s+ve\s+talep", f):
        return True
    # very permissive fallback for mojibake variants
    if "talep" in f and ("net" in f or "sonuc" in f):
        return True
    return False


def _to_ascii_tr(s: str) -> str:
    """
    Turkish-specific ASCII transliteration for filenames.
    """
    if not s:
        return ""
    table = str.maketrans(
        {
            "ç": "c",
            "Ç": "C",
            "ğ": "g",
            "Ğ": "G",
            "ı": "i",
            "İ": "I",
            "ö": "o",
            "Ö": "O",
            "ş": "s",
            "Ş": "S",
            "ü": "u",
            "Ü": "U",
        }
    )
    return s.translate(table)


def _safe_windows_filename_stem(s: str) -> str:
    """
    Windows-safe ASCII filename stem.
    Turkish chars are transliterated to ASCII.
    """
    s = (s or "").strip()
    if not s:
        return "dilekce"
    # Enforce ASCII-only naming for cross-platform compatibility.
    s = _to_ascii_tr(s)
    s = s.encode("ascii", "ignore").decode("ascii")
    # Remove Windows reserved characters: \ / : * ? " < > |
    s = re.sub(r'[\\\\/:*?"<>|]+', " ", s)
    # Drop control chars
    s = re.sub(r"[\x00-\x1F\x7F]+", " ", s)
    # Collapse whitespace
    s = re.sub(r"\s+", " ", s).strip()
    # Prefer hyphen separators
    s = s.replace(" _ ", " ").replace("_", " ")
    s = re.sub(r"\s*-\s*", " - ", s).strip()
    # Avoid trailing dots/spaces
    s = s.rstrip(". ").strip()
    # Limit length
    return (s[:140] if len(s) > 140 else s) or "dilekce"


def _clean_court_name_for_filename(court: str) -> str:
    """
    Remove Turkish hitap suffixes like "...'ne/...'na" that are common in court titles,
    because after ASCII transliteration they may appear as a trailing standalone "ne/na"
    token (e.g., "Hakimligi ne").
    """
    s = (court or "").strip()
    if not s:
        return ""
    # Normalize whitespace
    s = re.sub(r"\s+", " ", s).strip()
    # Remove trailing apostrophe-based suffix: "…'ne" / "…’ne" / "…'na" / "…’na"
    s = re.sub(r"[’']\s*n[ea]\s*$", "", s, flags=re.IGNORECASE).strip()
    return s


def _normalize_docx_filename(preferred: str) -> str:
    """
    Normalize a user/agent-provided filename to an ASCII, Windows-safe .docx filename.
    """
    name = (preferred or "").strip()
    if not name:
        return ""
    if not name.lower().endswith(".docx"):
        name = name + ".docx"
    stem = name[:-5].strip()
    stem = _safe_windows_filename_stem(stem)
    # Avoid Windows reserved device names (case-insensitive)
    reserved = {
        "con",
        "prn",
        "aux",
        "nul",
        "com1",
        "com2",
        "com3",
        "com4",
        "com5",
        "com6",
        "com7",
        "com8",
        "com9",
        "lpt1",
        "lpt2",
        "lpt3",
        "lpt4",
        "lpt5",
        "lpt6",
        "lpt7",
        "lpt8",
        "lpt9",
    }
    if stem.strip().lower() in reserved:
        stem = "_" + stem
    return f"{stem}.docx"

def _project_root() -> Path:
    # backend root: .../src/petitions/pipeline.py -> backend/
    return Path(__file__).resolve().parents[2]

def _load_pack_schema(name: str) -> Dict[str, Any]:
    root = _project_root()
    # Canonical (keep petition assets together)
    p_new = root / "src" / "petitions" / "schemas" / name
    if not p_new.exists():
        raise PetitionPipelineError(f"schema_not_found: {name}")
    return json.loads(_read_text(p_new))

def _validate(schema: Dict[str, Any], obj: Dict[str, Any]) -> None:
    v = Draft202012Validator(schema)
    errs = sorted(v.iter_errors(obj), key=lambda e: e.path)
    if errs:
        msg = "; ".join([f"{'/'.join([str(x) for x in e.path])}: {e.message}" for e in errs[:8]])
        raise PetitionPipelineError(f"schema_validation_failed: {msg}")


def _parse_date_to_iso(s: str) -> str | None:
    """
    Best-effort normalization to YYYY-MM-DD.
    Accepts: YYYY-MM-DD, DD.MM.YYYY, DD/MM/YYYY, DD-MM-YYYY.
    """
    t = (s or "").strip()
    if not t:
        return None
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", t):
        return t
    m = re.fullmatch(r"(\d{2})[./-](\d{2})[./-](\d{4})", t)
    if m:
        dd, mm, yyyy = m.group(1), m.group(2), m.group(3)
        return f"{yyyy}-{mm}-{dd}"
    return None


def _ensure_required_sections_inplace(obj: Dict[str, Any]) -> None:
    required = ["AÇIKLAMALAR", "DELİLLER", "HUKUKİ SEBEPLER", "NETİCE VE TALEP"]
    sections = obj.get("sections")
    if not isinstance(sections, list):
        return
    existing = {_fold_tr((s.get("title") if isinstance(s, dict) else "") or "") for s in sections if isinstance(s, dict)}
    for title in required:
        if _fold_tr(title) in existing:
            continue
        sections.append({"title": title, "blocks": [{"kind": "paragraph", "text": ""}]})


def _ensure_yargilama_gideri_item_inplace(items: list[str]) -> None:
    for it in items:
        f = _fold_tr(it)
        if "yargilama gider" in f and ("vekalet ucret" in f or "vekâlet ucret" in f):
            return
    items.append("Yargılama giderleri ile vekâlet ücretinin karşı tarafa yükletilmesine,")


def _fix_netice_ve_talep_inplace(obj: Dict[str, Any]) -> None:
    sections = obj.get("sections")
    if not isinstance(sections, list):
        return
    netice = None
    for s in sections:
        if isinstance(s, dict) and _is_netice_title(s.get("title")):
            netice = s
            break
    if not isinstance(netice, dict):
        return
    blocks = netice.get("blocks")
    if not isinstance(blocks, list):
        return

    # Ensure opening transition paragraph
    want_open = "Yukarıda açıklanan nedenlerle;"
    has_open = False
    for bl in blocks[:3]:
        if not isinstance(bl, dict):
            continue
        if bl.get("kind") != "paragraph":
            continue
        t = str(bl.get("text") or "").strip()
        if "yukarida aciklanan nedenlerle" in _fold_tr(t):
            has_open = True
            break
    if not has_open:
        blocks.insert(0, {"kind": "paragraph", "text": want_open})

    # Clean list items (avoid blank numbering)
    for bl in blocks:
        if not isinstance(bl, dict):
            continue
        if bl.get("kind") in {"numbered", "bullets"} and isinstance(bl.get("text"), list):
            bl["text"] = [str(x).strip() for x in bl["text"] if str(x).strip()]

    # Ensure numbered exists (promote bullets if needed)
    numbered = None
    for bl in blocks:
        if isinstance(bl, dict) and bl.get("kind") == "numbered" and isinstance(bl.get("text"), list):
            numbered = bl
            break
    if numbered is None:
        for bl in blocks:
            if isinstance(bl, dict) and bl.get("kind") == "bullets" and isinstance(bl.get("text"), list):
                bl["kind"] = "numbered"
                numbered = bl
                break

    if isinstance(numbered, dict) and isinstance(numbered.get("text"), list):
        items = [str(x).strip() for x in numbered.get("text") if str(x).strip()]
        if items:
            _ensure_yargilama_gideri_item_inplace(items)
            numbered["text"] = items

    # Ensure closing paragraph exists
    want_close = "Arz ve talep ederim."
    tail_para = None
    for bl in reversed(blocks):
        if isinstance(bl, dict) and bl.get("kind") == "paragraph":
            tail_para = str(bl.get("text") or "").strip()
            break
    if _fold_tr(tail_para or "") not in {_fold_tr("Arz ve talep ederim."), _fold_tr("Vekâleten arz ve talep ederim.")}:
        blocks.append({"kind": "paragraph", "text": want_close})


def _post_validate_and_autofix_inplace(obj: Dict[str, Any]) -> None:
    """
    Deterministic, schema-safe repairs.
    Does NOT add new information; only enforces structure/format guarantees.
    """
    _ensure_required_sections_inplace(obj)
    meta = obj.get("meta")
    if isinstance(meta, dict) and isinstance(meta.get("date"), str):
        iso = _parse_date_to_iso(str(meta.get("date") or ""))
        if iso:
            meta["date"] = iso
    _fix_netice_ve_talep_inplace(obj)


def _pre_validate_soft_normalize_inplace(obj: Dict[str, Any]) -> None:
    """
    Best-effort cleanup for common LLM output shape mistakes.
    This runs before schema validation and should only coerce/drop obviously invalid
    values without inventing substantive content.
    """
    meta = obj.get("meta")
    if isinstance(meta, dict):
        style = meta.get("style")
        if isinstance(style, str):
            # Models sometimes emit stylistic prose like "resmi" / "resmî ve ikna edici".
            # Renderer already uses defaults, so drop prose strings instead of failing.
            stripped = style.strip()
            if not stripped:
                meta.pop("style", None)
            else:
                meta["style"] = {}
        elif style is not None and not isinstance(style, dict):
            meta.pop("style", None)

    header_blocks = obj.get("header_blocks")
    if isinstance(header_blocks, list):
        for block in header_blocks:
            if not isinstance(block, dict):
                continue
            style = block.get("style")
            if style is not None and not isinstance(style, dict):
                block.pop("style", None)


def normalize_output_obj(obj: Dict[str, Any]) -> tuple[Dict[str, Any], str]:
    if not isinstance(obj, dict):
        raise PetitionPipelineError("invalid_output_json: top_level_must_be_object")
    output_schema = _load_pack_schema("output.schema.json")
    _pre_validate_soft_normalize_inplace(obj)
    _validate(output_schema, obj)
    _post_validate_and_autofix_inplace(obj)
    _validate(output_schema, obj)
    output_json_norm = json.dumps(obj, ensure_ascii=False)
    return obj, output_json_norm


def parse_and_normalize_output_json(raw: str) -> tuple[Dict[str, Any], str]:
    payload = str(raw or "").strip()
    if not payload:
        raise PetitionPipelineError("invalid_output_json: empty")
    try:
        obj_any = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise PetitionPipelineError(
            "invalid_output_json: JSONDecodeError (petition_json MUST be a single valid JSON object string; "
            "no markdown/code fences/extra text)"
        ) from exc
    except Exception as exc:
        raise PetitionPipelineError(f"invalid_output_json: {type(exc).__name__}") from exc
    if not isinstance(obj_any, dict):
        raise PetitionPipelineError("invalid_output_json: top_level_must_be_object")
    return normalize_output_obj(obj_any)


def _build_summary_text(output: Dict[str, Any], *, petition_id: int, version_id: int, filename: str) -> str:
    """
    Simple, non-LLM summary: small, stable, good for main agent context.
    """
    meta = output.get("meta") if isinstance(output.get("meta"), dict) else {}
    court = (meta.get("court") or "").strip()
    doc_type = (meta.get("document_type") or "").strip()
    date = (meta.get("date") or "").strip()
    assumptions = meta.get("assumptions") if isinstance(meta.get("assumptions"), list) else []
    missing = meta.get("missing_fields") if isinstance(meta.get("missing_fields"), list) else []

    parties: list[str] = []
    for hb in output.get("header_blocks") or []:
        if not isinstance(hb, dict):
            continue
        lab = (hb.get("label") or "").strip()
        val = (hb.get("value") or "").strip()
        if lab.lower() in {"davacı", "şikayetçi", "başvuran", "davali", "davalı", "şüpheli", "idare", "vekili", "müdahil"}:
            if val:
                parties.append(f"{lab}: {val}")

    reqs: list[str] = []
    for s in output.get("sections") or []:
        if not isinstance(s, dict):
            continue
        if not _is_netice_title(s.get("title")):            continue
        for bl in s.get("blocks") or []:
            if not isinstance(bl, dict):
                continue
            if bl.get("kind") == "numbered" and isinstance(bl.get("text"), list):
                for item in bl["text"][:8]:
                    reqs.append(str(item))

    lines: list[str] = []
    # User-facing summary should not leak internal IDs.
    lines.append(f"DİLEKÇE hazır: dosya={filename}")
    if court:
        lines.append(f"Mahkeme/Makam: {court}")
    if doc_type:
        lines.append(f"Dilekçe türü: {doc_type}")
    if date:
        lines.append(f"Tarih: {date}")
    if parties:
        lines.append("Taraflar:")
        for p in parties[:6]:
            lines.append(f"- {p}")
    if reqs:
        lines.append("Talepler (Netice ve Talep):")
        for i, r in enumerate(reqs[:10], start=1):
            lines.append(f"{i}) {r}")
    if assumptions:
        lines.append("Varsayımlar:")
        for a in assumptions[:8]:
            lines.append(f"- {str(a)}")
    if missing:
        lines.append("Eksik Bilgiler:")
        for m in missing[:12]:
            lines.append(f"- {str(m)}")
    return "\n".join(lines).strip()


@dataclass(frozen=True)
class PetitionArtifacts:
    output_obj: Dict[str, Any]
    output_json: str
    docx_bytes: bytes
    docx_filename: str
    udf_bytes: bytes
    udf_filename: str
    summary_text: str


_HEADER_BLOCK_VALUE_PATH_RE = re.compile(r"^header_blocks\.(\d+)\.value$")
_SECTION_TITLE_PATH_RE = re.compile(r"^sections\.(\d+)\.title$")
_SECTION_BLOCK_TEXT_PATH_RE = re.compile(r"^sections\.(\d+)\.blocks\.(\d+)\.text$")
_SIGNATURE_PATH_RE = re.compile(r"^signature\.(name_line|phrase|place_date_line)$")


def _value_preview(value: Any) -> str:
    if isinstance(value, list):
        return "\n".join(str(x).strip() for x in value if str(x).strip()).strip()
    return str(value or "").strip()


def build_preview_locators(output_obj: Dict[str, Any]) -> Dict[str, Any]:
    locators: Dict[str, Any] = {
        "header_blocks": [],
        "sections": [],
        "signature": [],
        "attachments": {
            "node_id": "attachments",
            "field_path": "attachments",
            "items": [str(x).strip() for x in (output_obj.get("attachments") or []) if str(x).strip()],
        },
    }

    for idx, block in enumerate(output_obj.get("header_blocks") or []):
        if not isinstance(block, dict):
            continue
        value = block.get("value")
        locators["header_blocks"].append(
            {
                "node_id": f"header_blocks.{idx}",
                "field_path": f"header_blocks.{idx}.value",
                "label": str(block.get("label") or ""),
                "text_preview": _value_preview(value),
                "is_list": isinstance(value, list),
            }
        )

    for sec_idx, section in enumerate(output_obj.get("sections") or []):
        if not isinstance(section, dict):
            continue
        section_title = str(section.get("title") or "")
        section_entry: Dict[str, Any] = {
            "section_index": int(sec_idx),
            "title": section_title,
            "title_node": {
                "node_id": f"sections.{sec_idx}.title",
                "field_path": f"sections.{sec_idx}.title",
                "text_preview": section_title,
            },
            "blocks": [],
        }
        for block_idx, block in enumerate(section.get("blocks") or []):
            if not isinstance(block, dict):
                continue
            text = block.get("text")
            section_entry["blocks"].append(
                {
                    "node_id": f"sections.{sec_idx}.blocks.{block_idx}",
                    "field_path": f"sections.{sec_idx}.blocks.{block_idx}.text",
                    "kind": str(block.get("kind") or ""),
                    "section_title": section_title,
                    "text_preview": _value_preview(text),
                    "is_list": isinstance(text, list),
                }
            )
        locators["sections"].append(section_entry)

    signature = output_obj.get("signature") if isinstance(output_obj.get("signature"), dict) else {}
    for key in ("name_line", "phrase", "place_date_line"):
        value = signature.get(key)
        if value is None:
            continue
        locators["signature"].append(
            {
                "node_id": f"signature.{key}",
                "field_path": f"signature.{key}",
                "label": key,
                "text_preview": _value_preview(value),
            }
        )
    return locators


def build_preview_response(row: Dict[str, Any]) -> Dict[str, Any]:
    output_obj, _output_json_norm = parse_and_normalize_output_json(str(row.get("output_json") or ""))
    return {
        "petition_id": int(row["petition_id"]),
        "status": row.get("status"),
        "version": {
            "version_id": int(row["version_id"]),
            "version_no": int(row["version_no"]),
            "docx_filename": row.get("docx_filename"),
            "summary_text": row.get("summary_text"),
            "created_at": row.get("created_at"),
            "updated_at": row.get("petition_updated_at"),
        },
        "document": deepcopy(output_obj),
        "locators": build_preview_locators(output_obj),
    }


def _normalize_string_list(value: Any, *, field_path: str) -> list[str]:
    if isinstance(value, str):
        stripped = value.strip()
        return [stripped] if stripped else []
    if not isinstance(value, list):
        raise PetitionPipelineError(f"patch_validation_failed: {field_path} must be string or string[]")
    out: list[str] = []
    for item in value:
        if not isinstance(item, str):
            raise PetitionPipelineError(f"patch_validation_failed: {field_path} items must be strings")
        stripped = item.strip()
        if stripped:
            out.append(stripped)
    return out


def get_field_text(output_obj: Dict[str, Any], field_path: str) -> str:
    value = get_field_value(output_obj, field_path)
    return _value_preview(value)


def get_field_value(output_obj: Dict[str, Any], field_path: str) -> Any:
    path = str(field_path or "").strip()
    if not path:
        raise PetitionPipelineError("invalid_field_path: empty")
    m = _HEADER_BLOCK_VALUE_PATH_RE.fullmatch(path)
    if m:
        idx = int(m.group(1))
        blocks = output_obj.get("header_blocks")
        if not isinstance(blocks, list) or idx >= len(blocks) or not isinstance(blocks[idx], dict):
            raise PetitionPipelineError(f"invalid_field_path: {path}")
        return blocks[idx].get("value")
    m = _SECTION_TITLE_PATH_RE.fullmatch(path)
    if m:
        sec_idx = int(m.group(1))
        sections = output_obj.get("sections")
        if not isinstance(sections, list) or sec_idx >= len(sections) or not isinstance(sections[sec_idx], dict):
            raise PetitionPipelineError(f"invalid_field_path: {path}")
        return sections[sec_idx].get("title")
    m = _SECTION_BLOCK_TEXT_PATH_RE.fullmatch(path)
    if m:
        sec_idx = int(m.group(1))
        block_idx = int(m.group(2))
        sections = output_obj.get("sections")
        if not isinstance(sections, list) or sec_idx >= len(sections) or not isinstance(sections[sec_idx], dict):
            raise PetitionPipelineError(f"invalid_field_path: {path}")
        blocks = sections[sec_idx].get("blocks")
        if not isinstance(blocks, list) or block_idx >= len(blocks) or not isinstance(blocks[block_idx], dict):
            raise PetitionPipelineError(f"invalid_field_path: {path}")
        return blocks[block_idx].get("text")
    m = _SIGNATURE_PATH_RE.fullmatch(path)
    if m:
        signature = output_obj.get("signature")
        if not isinstance(signature, dict):
            raise PetitionPipelineError(f"invalid_field_path: {path}")
        return signature.get(m.group(1))
    if path == "attachments":
        return output_obj.get("attachments") or []
    raise PetitionPipelineError(f"invalid_field_path: {path}")


def apply_patch_operations(output_obj: Dict[str, Any], patches: list[Dict[str, Any]]) -> tuple[Dict[str, Any], str]:
    if not isinstance(patches, list) or not patches:
        raise PetitionPipelineError("patch_validation_failed: patches_required")

    updated = deepcopy(output_obj)
    for op in patches:
        if not isinstance(op, dict):
            raise PetitionPipelineError("patch_validation_failed: each patch must be an object")
        path = str(op.get("field_path") or "").strip()
        if not path:
            raise PetitionPipelineError("patch_validation_failed: field_path_required")
        value = op.get("value")

        m = _HEADER_BLOCK_VALUE_PATH_RE.fullmatch(path)
        if m:
            idx = int(m.group(1))
            blocks = updated.get("header_blocks")
            if not isinstance(blocks, list) or idx >= len(blocks) or not isinstance(blocks[idx], dict):
                raise PetitionPipelineError(f"invalid_field_path: {path}")
            if not isinstance(value, str):
                raise PetitionPipelineError(f"patch_validation_failed: {path} must be a string")
            blocks[idx]["value"] = value.strip()
            continue

        m = _SECTION_TITLE_PATH_RE.fullmatch(path)
        if m:
            sec_idx = int(m.group(1))
            sections = updated.get("sections")
            if not isinstance(sections, list) or sec_idx >= len(sections) or not isinstance(sections[sec_idx], dict):
                raise PetitionPipelineError(f"invalid_field_path: {path}")
            if not isinstance(value, str):
                raise PetitionPipelineError(f"patch_validation_failed: {path} must be a string")
            sections[sec_idx]["title"] = value.strip()
            continue

        m = _SECTION_BLOCK_TEXT_PATH_RE.fullmatch(path)
        if m:
            sec_idx = int(m.group(1))
            block_idx = int(m.group(2))
            sections = updated.get("sections")
            if not isinstance(sections, list) or sec_idx >= len(sections) or not isinstance(sections[sec_idx], dict):
                raise PetitionPipelineError(f"invalid_field_path: {path}")
            blocks = sections[sec_idx].get("blocks")
            if not isinstance(blocks, list) or block_idx >= len(blocks) or not isinstance(blocks[block_idx], dict):
                raise PetitionPipelineError(f"invalid_field_path: {path}")
            block = blocks[block_idx]
            kind = str(block.get("kind") or "").strip()
            if kind in {"numbered", "bullets"}:
                block["text"] = _normalize_string_list(value, field_path=path)
            else:
                if not isinstance(value, str):
                    raise PetitionPipelineError(f"patch_validation_failed: {path} must be a string")
                block["text"] = value.strip()
            continue

        m = _SIGNATURE_PATH_RE.fullmatch(path)
        if m:
            signature = updated.get("signature")
            if not isinstance(signature, dict):
                raise PetitionPipelineError(f"invalid_field_path: {path}")
            if not isinstance(value, str):
                raise PetitionPipelineError(f"patch_validation_failed: {path} must be a string")
            signature[m.group(1)] = value.strip()
            continue

        if path == "attachments":
            updated["attachments"] = _normalize_string_list(value, field_path=path)
            continue

        raise PetitionPipelineError(f"invalid_field_path: {path}")

    return normalize_output_obj(updated)


async def generate_petition_artifacts_from_output_json(
    *,
    output_json: str,
    preferred_filename: Optional[str] = None,
) -> PetitionArtifacts:
    """
    No-LLM path:
    - Accept already-prepared petition JSON from main agent
    - Validate against schema
    - Apply deterministic post-fixes
    - Render DOCX/UDF artifacts
    """
    raw = str(output_json or "").strip()
    obj, output_json_norm = parse_and_normalize_output_json(raw)
    docx_bytes = render_docx_bytes(obj)
    udf_bytes = render_udf_bytes(output=obj, include_documentproperties=False)

    meta = obj.get("meta") if isinstance(obj.get("meta"), dict) else {}
    court = _clean_court_name_for_filename(str(meta.get("court") or "dilekce"))
    doc_type = (meta.get("document_type") or "").strip()
    date = (meta.get("date") or "").strip()
    stem_parts = []
    if court:
        stem_parts.append(court)
    if doc_type:
        stem_parts.append(doc_type)
    if date:
        stem_parts.append(date)
    stem = _safe_windows_filename_stem(" - ".join(stem_parts))
    docx_filename = _normalize_docx_filename(str(preferred_filename or ""))
    if not docx_filename:
        docx_filename = f"{stem}.docx"
    udf_filename = docx_filename[:-5] + ".udf" if docx_filename.lower().endswith(".docx") else (docx_filename + ".udf")

    return PetitionArtifacts(
        output_obj=obj,
        output_json=output_json_norm,
        docx_bytes=docx_bytes,
        docx_filename=docx_filename,
        udf_bytes=udf_bytes,
        udf_filename=udf_filename,
        summary_text="",
    )


def build_summary_text(output_obj: Dict[str, Any], *, petition_id: int, version_id: int, filename: str) -> str:
    return _build_summary_text(output_obj, petition_id=int(petition_id), version_id=int(version_id), filename=filename)


