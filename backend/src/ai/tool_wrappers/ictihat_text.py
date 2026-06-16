from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Iterable, List


@dataclass(frozen=True)
class StitchResult:
    text: str
    truncated: bool


_PUNCT_STRIP = "\"'“”‘’`´.,;:!?()[]{}<>|/\\…—–-•·"

# Stitching tunables are intentionally NOT configurable via env.
# If we need to revisit these, we change code (and keep behavior consistent across environments).
_STITCH_MAX_WORDS = 160
_STITCH_MIN_WORDS = 6
_STITCH_MAX_SKIP_START_WORDS = 24
_STITCH_MAX_SKIP_END_WORDS = 12
_STITCH_TAIL_WINDOW_CHARS = 24000


def _norm_token(tok: str) -> str:
    """
    Normalize a token for overlap matching:
    - strip surrounding punctuation
    - casefold for robust matching
    """
    if not isinstance(tok, str):
        tok = str(tok)
    t = tok.strip(_PUNCT_STRIP).strip()
    return t.casefold()


def _token_spans(text: str) -> list[tuple[int, int, str]]:
    """
    Return list of (start, end, token) for non-whitespace spans.
    """
    if not isinstance(text, str) or not text:
        return []
    return [(m.start(), m.end(), m.group(0)) for m in re.finditer(r"\S+", text)]


def _dedup_repeated_prefix_block(text: str, *, k_tokens: int = 30, search_window_tokens: int = 140) -> str:
    """
    If `text` starts with a block that appears again shortly after (common in overlapped chunk exports),
    drop the first block and keep the later occurrence.

    We detect this by token-sequence matching: find the first K normalized tokens, then locate the same
    sequence again within the next `search_window_tokens` tokens.
    """
    if not isinstance(text, str) or not text.strip():
        return text
    spans = _token_spans(text)
    if len(spans) < 20:
        return text

    toks: list[str] = []
    starts: list[int] = []
    for s, _e, tok in spans:
        nt = _norm_token(tok)
        if nt:
            toks.append(nt)
            starts.append(int(s))
    if len(toks) < 20:
        return text

    k = max(10, min(int(k_tokens), len(toks) // 2))
    pat = toks[:k]
    max_p = min(len(toks) - k, int(search_window_tokens))
    for p in range(3, max_p + 1):
        if toks[p : p + k] == pat:
            cut = starts[p] if 0 <= p < len(starts) else 0
            if cut > 0:
                return text[cut:].lstrip()
    return text


def _drop_partial_leading_token_if_suffix(
    prev: str,
    nxt: str,
    *,
    max_prev_tokens: int = 24,
    tail_window_chars: int = 2400,
) -> str:
    """
    If `nxt` appears to start mid-word (its first token is a suffix of one of the last tokens in `prev`),
    drop that first token from `nxt`.

    Example:
      prev tail contains:  "devredildiğinin belirlendiği ..."
      nxt starts with:     "ildiğinin belirlendiği ..."
    """
    if not isinstance(prev, str) or not isinstance(nxt, str):
        return nxt
    s = nxt.lstrip()
    if not s:
        return nxt
    # Look at a tail window of `prev` (not just last tokens) because the chunk may start mid-word
    # but the corresponding full token can appear a bit earlier in the tail sentence.
    tw = max(200, int(tail_window_chars))
    prev_tail = prev[-tw:] if len(prev) > tw else prev
    prev_sp = _token_spans(prev_tail)
    nxt_sp = _token_spans(s)
    if not prev_sp or not nxt_sp:
        return nxt

    first_tok = nxt_sp[0][2]
    first_norm = _norm_token(first_tok)
    if len(first_norm) < 4:
        return nxt

    tail = prev_sp[-max(1, int(max_prev_tokens)) :]
    for _s, _e, tok in reversed(tail):
        tnorm = _norm_token(tok)
        if not tnorm:
            continue
        # Must be a proper suffix (not equal) and noticeably shorter.
        if tnorm != first_norm and tnorm.endswith(first_norm) and (len(tnorm) - len(first_norm)) >= 3:
            cut = int(nxt_sp[0][1])
            return s[cut:].lstrip()

    return nxt


def _find_overlap(prev: str, nxt: str, *, window: int = 1600, min_overlap: int = 60) -> int:
    """
    Return overlap length k such that prev[-k:] == nxt[:k], searching within `window`.
    This is meant to remove chunk overlap produced by sliding-window chunking.
    """
    if not prev or not nxt:
        return 0
    window = max(200, int(window))
    min_overlap = max(10, int(min_overlap))

    tail = prev[-window:]
    head = nxt[:window]

    def _kmp_prefix(s: str) -> list[int]:
        # Standard prefix-function (pi) in O(n)
        pi = [0] * len(s)
        j = 0
        for i in range(1, len(s)):
            while j > 0 and s[i] != s[j]:
                j = pi[j - 1]
            if s[i] == s[j]:
                j += 1
                pi[i] = j
        return pi

    def _overlap_kmp(h: str, t: str) -> int:
        # Longest prefix of h that is also a suffix of t.
        if not h or not t:
            return 0
        # Sentinel must not appear in natural text; NUL is safe for our inputs.
        combined = h + "\x00" + t
        pi = _kmp_prefix(combined)
        k = int(pi[-1]) if pi else 0
        # Ensure we don't return overlaps that include the sentinel boundary.
        if k > len(h):
            k = len(h)
        return k

    k = _overlap_kmp(head, tail)
    if k >= min_overlap:
        return k

    # Small extra: tolerate boundary whitespace differences (common at chunk edges)
    tail2 = tail.rstrip()
    head2 = head.lstrip()
    k2 = _overlap_kmp(head2, tail2)
    if k2 >= min_overlap:
        # We matched after stripping; approximate overlap on original by k (safe enough).
        return int(k2)

    return 0


def _find_overlap_word_cut_offset(
    prev: str,
    nxt: str,
    *,
    max_words: int = 240,
    min_words: int = 12,
    max_skip_start_words: int = 60,
    max_skip_end_words: int = 30,
    tail_window_chars: int = 12000,
) -> int:
    """
    Find an overlap by comparing the last K normalized tokens of `prev` with
    the first K normalized tokens of `nxt`. If found, return the CUT OFFSET in
    `nxt` (character index) to remove the overlapping prefix.
    """
    if not prev or not nxt:
        return 0

    max_words = max(40, int(max_words))
    min_words = max(4, int(min_words))

    # Tokenizing the whole accumulated decision text on every chunk merge becomes
    # prohibitively expensive for very large decisions. We only need the tail of
    # the previous chunked text to detect overlap against the next chunk head.
    prev_tail_window = max(2000, int(tail_window_chars))
    prev_tail = prev[-prev_tail_window:] if len(prev) > prev_tail_window else prev

    prev_sp = _token_spans(prev_tail)
    nxt_sp = _token_spans(nxt)
    if not prev_sp or not nxt_sp:
        return 0

    # Build normalized token arrays (drop empty normalized tokens).
    prev_norm: list[str] = []
    for _s, _e, tok in prev_sp[-max_words:]:
        nt = _norm_token(tok)
        if nt:
            prev_norm.append(nt)

    nxt_norm: list[str] = []
    nxt_end_offsets: list[int] = []
    for _s, e, tok in nxt_sp[:max_words]:
        nt = _norm_token(tok)
        if nt:
            nxt_norm.append(nt)
            nxt_end_offsets.append(int(e))

    if not prev_norm or not nxt_norm:
        return 0

    max_skip_start_words = max(0, int(max_skip_start_words))
    max_skip_start_words = min(max_skip_start_words, max(0, len(nxt_norm) - min_words))
    max_skip_end_words = max(0, int(max_skip_end_words))
    max_skip_end_words = min(max_skip_end_words, max(0, len(prev_norm) - min_words))

    # Allow skipping a few leading tokens of nxt (common when chunk starts mid-word or mid-sentence),
    # and also skipping a few trailing tokens of prev (common when prev ends mid-word).
    #
    # Performance note:
    # The previous implementation used nested slice comparisons (O(n^3) worst-case) + a difflib fallback.
    # That was expensive on some large chunks. We now compute overlap length using a KMP prefix-function
    # on token sequences, which is O(n) per (p,e) pair and fast enough for our bounded windows.

    _SENTINEL = object()

    def _kmp_prefix(seq: list[object]) -> list[int]:
        pi = [0] * len(seq)
        j = 0
        for i in range(1, len(seq)):
            while j > 0 and seq[i] != seq[j]:
                j = pi[j - 1]
            if seq[i] == seq[j]:
                j += 1
                pi[i] = j
        return pi

    def _overlap_kmp(prefix_seq: list[object], suffix_seq: list[object]) -> int:
        # Longest prefix of prefix_seq that is also a suffix of suffix_seq.
        if not prefix_seq or not suffix_seq:
            return 0
        combined: list[object] = prefix_seq + [_SENTINEL] + suffix_seq
        pi = _kmp_prefix(combined)
        k = int(pi[-1]) if pi else 0
        if k > len(prefix_seq):
            k = len(prefix_seq)
        return k

    best_k = 0
    best_p = 0
    best_e = 0
    for e in range(0, max_skip_end_words + 1):
        prev_end = len(prev_norm) - e
        if prev_end <= 0:
            continue
        prev_tail = prev_norm[:prev_end]
        for p in range(0, max_skip_start_words + 1):
            nxt_head = nxt_norm[p:]
            if len(nxt_head) < min_words:
                continue
            k = _overlap_kmp(nxt_head, prev_tail)
            if k >= min_words and k > best_k:
                best_k = int(k)
                best_p = int(p)
                best_e = int(e)

    if best_k >= min_words:
        idx = best_p + best_k - 1
        cut = nxt_end_offsets[idx] if 0 <= idx < len(nxt_end_offsets) else 0
        return int(cut)

    return 0


def _tail_keep_chars() -> int:
    # Keep more than the overlap windows so exact + token overlap checks still
    # have enough context, while avoiding repeated work on the full stitched text.
    return max(_STITCH_TAIL_WINDOW_CHARS, 1600 * 4)


def _update_tail(prev_tail: str, appended: str, *, keep_chars: int) -> str:
    if not appended:
        return prev_tail[-keep_chars:] if len(prev_tail) > keep_chars else prev_tail
    if not prev_tail:
        return appended[-keep_chars:] if len(appended) > keep_chars else appended
    combined = prev_tail + appended
    return combined[-keep_chars:] if len(combined) > keep_chars else combined


def stitch_decision_text(
    parts: Iterable[str],
    *,
    limit_chars: int | None,
    overlap_window: int = 1600,
    min_overlap: int = 60,
) -> StitchResult:
    """
    Stitch ordered chunk texts into a single decision text while removing overlaps.
    Keeps newlines between non-overlapping chunks to preserve readability.
    """
    limit: int | None = None
    if limit_chars is not None:
        try:
            v = int(limit_chars)
        except Exception:
            v = 0
        # Treat <=0 as "no truncation" (unlimited).
        if v > 0:
            limit = max(2000, v)

    cleaned_parts: List[str] = []
    for raw in parts:
        if raw is None:
            continue
        s = raw if isinstance(raw, str) else str(raw)
        s = s.strip()
        if s:
            cleaned_parts.append(s)

    if not cleaned_parts:
        return StitchResult(text="", truncated=False)

    # Reference HTML spot checks showed that the previous, more aggressive
    # overlap profile could over-trim valid text on some decisions. Use a
    # single conservative profile that preserves text while staying fast.
    max_words = _STITCH_MAX_WORDS
    min_words_token = _STITCH_MIN_WORDS
    skip_start = _STITCH_MAX_SKIP_START_WORDS
    skip_end = _STITCH_MAX_SKIP_END_WORDS
    refine_loops = 1

    segments: List[str] = []
    tail = ""
    tail_keep = _tail_keep_chars()

    for s in cleaned_parts:
        if not segments:
            segments.append(s)
            tail = s[-tail_keep:] if len(s) > tail_keep else s
            continue

        current = tail

        # 1) Prefer exact suffix/prefix overlap (fast, best when chunks are clean).
        # Also try to correct "starts mid-word" chunk heads (common in some exports).
        s = _drop_partial_leading_token_if_suffix(current, s, max_prev_tokens=10)
        k = _find_overlap(current, s, window=int(overlap_window), min_overlap=int(min_overlap))
        if k > 0:
            suffix = s[k:].lstrip()
            # Exact overlap sometimes leaves a duplicated prefix block inside the remainder
            # (same overlap block exported twice). Clean it up similarly to the word-overlap path.
            suffix = _dedup_repeated_prefix_block(suffix, k_tokens=30, search_window_tokens=140)
            for _ in range(refine_loops):
                if not suffix:
                    break
                suffix = _drop_partial_leading_token_if_suffix(current, suffix, max_prev_tokens=24, tail_window_chars=2400)
                k2 = _find_overlap(current, suffix, window=int(overlap_window), min_overlap=int(min_overlap))
                if k2 > 0:
                    suffix = suffix[k2:].lstrip()
                    suffix = _dedup_repeated_prefix_block(suffix, k_tokens=30, search_window_tokens=140)
                    continue
                cut2 = _find_overlap_word_cut_offset(
                    current,
                    suffix,
                    max_words=max_words,
                    min_words=min_words_token,
                    max_skip_start_words=skip_start,
                    max_skip_end_words=skip_end,
                )
                if cut2 > 0:
                    suffix = suffix[cut2:].lstrip()
                    suffix = _dedup_repeated_prefix_block(suffix, k_tokens=30, search_window_tokens=140)
                    continue
                break

            append_text = ""
            if current and suffix:
                if not current[-1].isspace() and not suffix[0].isspace() and suffix[0] not in _PUNCT_STRIP:
                    append_text = " " + suffix
                else:
                    append_text = suffix
            else:
                append_text = suffix or ""
            if append_text:
                segments.append(append_text)
                tail = _update_tail(tail, append_text, keep_chars=tail_keep)
        else:
            # 2) Fallback: word-sequence overlap (tolerates whitespace/punctuation differences).
            cut = _find_overlap_word_cut_offset(
                current,
                s,
                max_words=max_words,
                min_words=min_words_token,
                max_skip_start_words=skip_start,
                max_skip_end_words=skip_end,
            )
            if cut > 0:
                suffix = s[cut:]
                # Some chunkers may duplicate the same overlapped prefix inside the chunk
                # (e.g. overlap block appears twice separated by newlines). Iteratively
                # trim again against the current tail.
                suffix = suffix.lstrip()
                # Also remove duplicated prefix blocks inside the chunk itself.
                suffix = _dedup_repeated_prefix_block(suffix, k_tokens=30, search_window_tokens=140)
                for _ in range(refine_loops):
                    if not suffix:
                        break
                    suffix = _drop_partial_leading_token_if_suffix(current, suffix, max_prev_tokens=10)
                    k2 = _find_overlap(current, suffix, window=int(overlap_window), min_overlap=int(min_overlap))
                    if k2 > 0:
                        suffix = suffix[k2:].lstrip()
                        continue
                    cut2 = _find_overlap_word_cut_offset(
                        current,
                        suffix,
                        max_words=max_words,
                        min_words=min_words_token,
                        max_skip_start_words=skip_start,
                        max_skip_end_words=skip_end,
                    )
                    if cut2 > 0:
                        suffix = suffix[cut2:].lstrip()
                        continue
                    break
                # Avoid accidental token-glue at boundary.
                append_text = ""
                if current and suffix:
                    if not current[-1].isspace() and not suffix[0].isspace() and suffix[0] not in _PUNCT_STRIP:
                        append_text = " " + suffix
                    else:
                        append_text = suffix
                else:
                    append_text = suffix or ""
                if append_text:
                    segments.append(append_text)
                    tail = _update_tail(tail, append_text, keep_chars=tail_keep)
            else:
                # Keep a paragraph break between unrelated chunks.
                if segments:
                    segments[-1] = segments[-1].rstrip()
                append_text = "\n" + s.lstrip()
                segments.append(append_text)
                tail = _update_tail(tail.rstrip(), append_text, keep_chars=tail_keep)

    stitched = "".join(segments).strip()
    truncated = False
    if limit is not None and len(stitched) > limit:
        stitched = stitched[: limit - 1] + "…"
        truncated = True

    return StitchResult(text=stitched, truncated=bool(truncated))

