"""Contrôle technique d'une liste de paramètres extraits.

Reprend la logique de run_agent (notebook, cellule #14), sans génération de texte.
Aucune interprétation médicale : uniquement présence des champs, cohérence
et position de la valeur par rapport à la fourchette du laboratoire.
"""
from __future__ import annotations

from app.identification.catalog import ACCEPTED_UNITS

from .reference import check_parameter, classify, plausible

REASONS = {
    "missing_unit": "unité absente du document",
    "unexpected_unit": "unité non reconnue",
    "missing_value": "valeur illisible",
    "invalid_reference": "fourchette incohérente",
    "implausible": "lecture incertaine (valeur très éloignée de la fourchette)",
}


def analyze_parameters(params: list[dict], method: str = "pdf_text") -> list[dict]:
    """Retourne une copie des paramètres enrichie de `status`, `reason_code`, `reason`.

    Un paramètre non fiable est marqué "not_analyzed" : il n'est jamais deviné.
    """
    known = [dict(p) for p in params if p["code"] in ACCEPTED_UNITS]

    blocked: dict[str, str] = {}
    for p in known:
        for issue in check_parameter(p, ACCEPTED_UNITS[p["code"]]):
            if issue["blocking"]:
                blocked.setdefault(p["code"], issue["issue"])

    if method == "ocr":  # garde-fou OCR (ex. virgule perdue : 128 au lieu de 1,28)
        for p in known:
            if p["code"] not in blocked and not plausible(p):
                blocked[p["code"]] = "implausible"

    for p in known:
        code = p["code"]
        if code in blocked:
            p["status"] = "not_analyzed"
            p["reason_code"] = blocked[code]
            p["reason"] = REASONS[blocked[code]]
        else:
            p["status"] = classify(p["value"], p["reference_min"], p["reference_max"])
            p["reason_code"] = None
            p["reason"] = None
    return known