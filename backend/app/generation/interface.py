"""Contrat du composant de génération d'explications.

Ce module ne contient aucune connaissance médicale ni règle métier :
il définit uniquement les structures d'entrée/sortie, l'interface abstraite
d'un générateur et les vérifications techniques d'ancrage des citations.
"""
from __future__ import annotations

from enum import Enum
from typing import Protocol, runtime_checkable

from pydantic import BaseModel, Field, model_validator

from app.schemas import DISCLAIMER, ParameterResult, Source


class ExplanationStatus(str, Enum):
    """État de disponibilité documentaire pour l'explication d'un paramètre."""

    grounded = "grounded"
    insufficient_sources = "insufficient_sources"
    not_analyzed = "not_analyzed"


class RetrievedPassage(BaseModel):
    """Passage documentaire issu d'une source vérifiée (fourni par le futur RAG)."""

    passage_id: str = Field(min_length=1)
    source: Source
    excerpt: str = Field(min_length=1)
    score: float | None = None


class ParameterExplanation(BaseModel):
    """Explication pédagogique associée à un paramètre biologique."""

    code: str = Field(min_length=1)
    status: ExplanationStatus
    text: str = Field(min_length=1)
    source_ids: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def check_citations_consistency(self) -> ParameterExplanation:
        if self.status == ExplanationStatus.grounded and not self.source_ids:
            raise ValueError(
                "Une explication au statut 'grounded' doit citer au moins un source_id."
            )
        if self.status != ExplanationStatus.grounded and self.source_ids:
            raise ValueError(
                "Une explication sans base documentaire suffisante ne doit pas citer de source_id."
            )
        return self


class GenerationRequest(BaseModel):
    """Entrée attendue par tout générateur d'explications."""

    parameters: list[ParameterResult] = Field(default_factory=list)
    passages: list[RetrievedPassage] = Field(default_factory=list)


class GenerationResult(BaseModel):
    """Sortie structurée du module de génération, alignée sur le contrat API v1."""

    summary: str | None = None
    parameter_explanations: list[ParameterExplanation] = Field(default_factory=list)
    sources: list[Source] = Field(default_factory=list)
    disclaimer: str = DISCLAIMER

    def to_task_explanations(self) -> dict:
        """Sérialise la partie explicative pour le champ `Task.explanations`."""
        return {
            "summary": self.summary,
            "parameter_explanations": [
                item.model_dump(mode="json") for item in self.parameter_explanations
            ],
        }


@runtime_checkable
class ExplanationGenerator(Protocol):
    """Interface à implémenter par tout générateur (repli neutre ou futur LLM+RAG)."""

    def generate(self, request: GenerationRequest) -> GenerationResult:
        """Produit des explications uniquement à partir de la requête fournie."""
        ...


def find_citation_errors(
    result: GenerationResult,
    passages: list[RetrievedPassage],
) -> list[str]:
    """Vérifie techniquement la cohérence entre citations, sources exposées et passages reçus."""
    errors: list[str] = []

    allowed_source_ids = {p.source.source_id for p in passages}
    exposed_source_ids = {s.source_id for s in result.sources}

    if result.disclaimer != DISCLAIMER:
        errors.append("Le disclaimer du résultat ne correspond pas au disclaimer officiel.")

    for src in result.sources:
        if src.source_id not in allowed_source_ids:
            errors.append(
                f"Source exposée absente des passages fournis : '{src.source_id}'."
            )

    for exp in result.parameter_explanations:
        for sid in exp.source_ids:
            if sid not in allowed_source_ids:
                errors.append(
                    f"Paramètre {exp.code} : source_id inconnu '{sid}'."
                )
            if sid not in exposed_source_ids:
                errors.append(
                    f"Paramètre {exp.code} : source_id '{sid}' cité mais absent de result.sources."
                )

    return errors