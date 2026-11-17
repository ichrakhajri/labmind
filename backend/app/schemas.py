"""Schémas de données partagés (base du contrat API v1).

Les champs `confidence` et `evidence.page` existent dans le contrat mais ne sont
pas encore calculés : ils valent None tant qu'aucun module ne les produit.
"""
from __future__ import annotations

from enum import Enum

from pydantic import BaseModel


class TaskStatus(str, Enum):
    received = "received"
    processing = "processing"
    waiting_for_user = "waiting_for_user"
    done = "done"
    error = "error"


class ExtractionMethod(str, Enum):
    pdf_text = "pdf_text"
    ocr = "ocr"


class ParameterStatus(str, Enum):
    below_reference = "below_reference"
    within_reference = "within_reference"
    above_reference = "above_reference"
    reference_unavailable = "reference_unavailable"
    value_unavailable = "value_unavailable"
    not_analyzed = "not_analyzed"


class Reference(BaseModel):
    min: float | None = None
    max: float | None = None
    origin: str | None = None  # "document_laboratoire" si une fourchette est présente


class Evidence(BaseModel):
    raw_text: str
    page: int | None = None  # non suivi pour l'instant


class ParameterResult(BaseModel):
    code: str
    name_printed: str
    value: float | None = None
    unit: str | None = None
    reference: Reference
    status: ParameterStatus
    reason: str | None = None        # renseigné si status = not_analyzed
    confidence: float | None = None  # non calculée pour l'instant
    evidence: Evidence


def parameter_from_dict(p: dict) -> ParameterResult:
    """Convertit un paramètre (dict issu de l'analyse) en schéma validé."""
    has_ref = p.get("reference_min") is not None or p.get("reference_max") is not None
    return ParameterResult(
        code=p["code"],
        name_printed=p["name_printed"],
        value=p.get("value"),
        unit=p.get("unit"),
        reference=Reference(
            min=p.get("reference_min"),
            max=p.get("reference_max"),
            origin="document_laboratoire" if has_ref else None,
        ),
        status=p["status"],
        reason=p.get("reason"),
        evidence=Evidence(raw_text=p.get("raw_line", "")),
    )