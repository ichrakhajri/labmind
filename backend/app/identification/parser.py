"""Identification des paramètres dans un texte extrait (regex + alias + pages)."""
from __future__ import annotations

import difflib
import re
import unicodedata

from .catalog import ALIASES, KNOWN_UNITS

NUM = r"\d+(?:[.,]\d+)?"
RANGE_RE = re.compile(rf"({NUM})\s*[-–—]\s*({NUM})")
UPPER_BOUND_RE = re.compile(
    rf"\(?\s*(?:r[ée]f\.?\s*:?\s*)?(?:<=?|inf[ée]rieur[e]?\s+[àa])\s*({NUM})"
    rf"(?:\s*[a-zA-Zµμ/%0-9^.,²]+)?\s*\)?",
    re.I,
)
LOWER_BOUND_RE = re.compile(
    rf"\(?\s*(?:r[ée]f\.?\s*:?\s*)?(?:>=?|sup[ée]rieur[e]?\s+[àa])\s*({NUM})"
    rf"(?:\s*[a-zA-Zµμ/%0-9^.,²]+)?\s*\)?",
    re.I,
)
NUM_RE = re.compile(NUM)


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFD", s.lower())
    return "".join(c for c in s if unicodedata.category(c) != "Mn")


_ALIAS_LIST = sorted(
    ((_norm(a), code) for code, al in ALIASES.items() for a in al),
    key=lambda x: -len(x[0]),
)


def to_float(s: str) -> float:
    return float(s.replace(",", "."))


def normalize_unit(u: str | None) -> str | None:
    """Nettoie l'unité et corrige les variantes typographiques et erreurs OCR."""
    if not u:
        return None
    u = u.strip().strip("()[]:;|_")
    u = re.sub(r"\s+", "", u).replace("μ", "µ")
    if not u:
        return None

    low = u.lower().replace("µ", "u").replace(",", ".")
    if re.match(r"^ml/min/1\.73m(?:\^?2|²)$", low):
        return "mL/min/1.73m²"

    exact = {k.lower().replace("µ", "u"): k for k in KNOWN_UNITS}
    if low in exact:
        return exact[low]

    m = re.match(r"^10\W?([36])/\w*l$", low)
    if m:
        return f"10^{m.group(1)}/µL"

    cand = difflib.get_close_matches(low, list(exact), n=1, cutoff=0.75)
    return exact[cand[0]] if cand else u


def match_alias(line: str) -> tuple[str | None, str | None]:
    """Retourne (code, texte_brut_correspondant) si un alias ouvre la ligne."""
    stripped = line.lstrip()
    norm_chars: list[str] = []
    orig_end_indices: list[int] = []

    for idx, ch in enumerate(stripped):
        decomposed = unicodedata.normalize("NFD", ch.lower())
        for sub in decomposed:
            if unicodedata.category(sub) != "Mn":
                norm_chars.append(sub)
                orig_end_indices.append(idx + 1)

    norm_line = "".join(norm_chars)
    for alias, code in _ALIAS_LIST:
        if re.match(rf"^{re.escape(alias)}(?=[\s:;|(\[]|$)", norm_line):
            raw_end = orig_end_indices[len(alias) - 1]
            return code, stripped[:raw_end]
    return None, None


def parse_line(line: str) -> dict | None:
    code, raw_alias = match_alias(line)
    if code is None or raw_alias is None:
        return None

    rest = line.lstrip()[len(raw_alias) :].lstrip(" :;|")
    ref_min = ref_max = None

    m = RANGE_RE.search(rest)
    if m:
        ref_min, ref_max = to_float(m.group(1)), to_float(m.group(2))
        rest = rest[: m.start()] + " " + rest[m.end() :]
    else:
        m_upper = UPPER_BOUND_RE.search(rest)
        if m_upper:
            ref_max = to_float(m_upper.group(1))
            rest = rest[: m_upper.start()] + " " + rest[m_upper.end() :]
        else:
            m_lower = LOWER_BOUND_RE.search(rest)
            if m_lower:
                ref_min = to_float(m_lower.group(1))
                rest = rest[: m_lower.start()] + " " + rest[m_lower.end() :]

    rest = re.sub(r"\(\s*r[ée]f\.?\s*:?\s*\)", " ", rest, flags=re.I)
    rest = re.sub(r"\(\s*\)", " ", rest)

    mv = NUM_RE.search(rest)
    if not mv:
        return None

    value = to_float(mv.group(0))
    unit_txt = (rest[: mv.start()] + " " + rest[mv.end() :]).strip()
    unit = normalize_unit(unit_txt) if unit_txt else None
    return {
        "code": code,
        "name_printed": raw_alias.strip(),
        "value": value,
        "unit": unit,
        "reference_min": ref_min,
        "reference_max": ref_max,
        "raw_line": line.strip(),
    }


def identify_parameters(text: str) -> list[dict]:
    out = []
    for line in text.splitlines():
        line = line.strip()
        if line:
            p = parse_line(line)
            if p:
                out.append(p)
    return out


def _completeness_score(param: dict) -> int:
    score = 0
    if param.get("value") is not None:
        score += 1
    if param.get("unit"):
        score += 1
    if param.get("reference_min") is not None or param.get("reference_max") is not None:
        score += 1
    return score


def identify_parameters_from_pages(pages: list[dict]) -> list[dict]:
    """Identifie les paramètres page par page (tableaux + texte) avec numéro de page."""
    results: list[dict] = []

    for page_info in pages:
        page_num = page_info.get("page")
        ocr_conf = page_info.get("ocr_confidence")
        page_candidates: dict[str, dict] = {}

        candidate_lines: list[str] = []
        candidate_lines.extend(page_info.get("table_rows") or [])
        candidate_lines.extend((page_info.get("text") or "").splitlines())

        for raw_line in candidate_lines:
            line = raw_line.strip()
            if not line:
                continue
            parsed = parse_line(line)
            if not parsed:
                continue

            parsed["page"] = page_num
            if ocr_conf is not None:
                parsed["source_ocr_confidence"] = ocr_conf

            code = parsed["code"]
            existing = page_candidates.get(code)
            if existing is None or _completeness_score(parsed) > _completeness_score(existing):
                page_candidates[code] = parsed

        results.extend(page_candidates.values())

    return results