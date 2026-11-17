"""Schémas de données partagés (base du contrat API v1).

Les champs `confidence` et `evidence.page` existent dans le contrat mais ne sont
pas encore calculés : ils valent None tant qu'aucun module ne les produit.
"""
from __future__ import annotations

from enum import Enum

from pydantic import BaseModel
from typing import Literal

from pydantic import Field

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
DISCLAIMER = ("Outil pédagogique : ce bilan ne remplace pas une consultation médicale "
              "et ne constitue ni un diagnostic ni une prescription.")


class DocumentInfo(BaseModel):
    filename: str
    extraction_method: ExtractionMethod | None = None


class PendingQuestion(BaseModel):
    question_id: str
    field: Literal["unit", "value", "reference_min", "reference_max"]
    code: str
    message: str
    options: list[str] = Field(default_factory=list)


class AnswerIn(BaseModel):
    question_id: str
    answer: str = Field(min_length=1, max_length=100)


class Source(BaseModel):
    """À venir (Étape 3) : défini pour figer le contrat."""
    source_id: str
    title: str
    organisme: str
    url: str
    date: str | None = None


class ErrorInfo(BaseModel):
    code: str
    message: str


class ErrorResponse(BaseModel):
    error: ErrorInfo


class Task(BaseModel):
    task_id: str
    status: TaskStatus
    document: DocumentInfo | None = None
    detected_categories: list[str] = Field(default_factory=list)
    parameters: list[ParameterResult] = Field(default_factory=list)
    pending_question: PendingQuestion | None = None
    report_id: str | None = None
    explanations: dict | None = None  # à venir (Étape 3)
    sources: list[Source] = Field(default_factory=list)
    disclaimer: str = DISCLAIMER
    errors: list[ErrorInfo] = Field(default_factory=list)