"""Identification des paramètres dans un texte extrait (regex + alias).

Code repris du notebook (cellule #6) sans changement de logique.
"""
from __future__ import annotations

import difflib
import re
import unicodedata

from .catalog import ALIASES, KNOWN_UNITS

NUM = r"\d+(?:[.,]\d+)?"
RANGE_RE = re.compile(rf"({NUM})\s*[-–—]\s*({NUM})")
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
    """Nettoie l'unité et corrige les erreurs OCR (10%3/uL -> 10^3/µL)."""
    if not u:
        return None
    u = u.strip().strip("()[]:;|_")
    u = re.sub(r"\s+", "", u).replace("μ", "µ")
    if not u:
        return None
    low = u.lower().replace("µ", "u")
    exact = {k.lower().replace("µ", "u"): k for k in KNOWN_UNITS}
    if low in exact:
        return exact[low]
    m = re.match(r"^10\W?([36])/\w*l$", low)
    if m:
        return f"10^{m.group(1)}/µL"
    cand = difflib.get_close_matches(low, list(exact), n=1, cutoff=0.7)
    return exact[cand[0]] if cand else u


def match_alias(line: str):
    n = _norm(line)
    for alias, code in _ALIAS_LIST:
        if re.match(rf"^{re.escape(alias)}(?=[\s:;|]|$)", n):
            return code, alias
    return None, None


def parse_line(line: str) -> dict | None:
    code, alias = match_alias(line)
    if code is None:
        return None
    rest = line[len(alias):].lstrip(" :;|") if len(line) >= len(alias) else ""
    ref_min = ref_max = None
    m = RANGE_RE.search(rest)
    if m:
        ref_min, ref_max = to_float(m.group(1)), to_float(m.group(2))
        rest = rest[:m.start()] + " " + rest[m.end():]
    rest = re.sub(r"\(\s*r[ée]f\.?\s*:?\s*\)", " ", rest, flags=re.I)
    mv = NUM_RE.search(rest)
    if not mv:
        return None
    value = to_float(mv.group(0))
    unit_txt = (rest[:mv.start()] + " " + rest[mv.end():]).strip()
    unit = normalize_unit(unit_txt) if unit_txt else None
    return {
        "code": code,
        "name_printed": line[:len(alias)].strip(),
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