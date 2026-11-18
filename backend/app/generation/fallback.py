"""Générateur de repli neutre lorsque les sources documentaires sont insuffisantes.

Remplace les anciens mécanismes de repli vers des conseils figés.
Ne contient aucune règle médicale ni différence de texte selon la position
arithmétique de la valeur (en dessous, dans, ou au-dessus de la référence).
"""
from __future__ import annotations

from app.schemas import DISCLAIMER, ParameterResult, ParameterStatus

from .interface import (
    ExplanationStatus,
    GenerationRequest,
    GenerationResult,
    ParameterExplanation,
)

INSUFFICIENT_SOURCES_SUMMARY = (
    "Aucune source documentaire vérifiée n'est disponible pour générer "
    "des explications pédagogiques pour ce bilan."
)

INSUFFICIENT_SOURCES_PARAMETER_MESSAGE = (
    "Information documentaire insuffisante : aucune source vérifiée "
    "n'est disponible pour expliquer ce paramètre."
)

NOT_ANALYZED_PARAMETER_MESSAGE = (
    "Paramètre non analysé : aucune explication ne peut être fournie "
    "tant que la donnée reste incomplète ou incertaine."
)


def build_unavailable_explanation(parameter: ParameterResult) -> ParameterExplanation:
    """Construit une entrée explicative neutre sans source documentaire."""
    if parameter.status == ParameterStatus.not_analyzed:
        if parameter.reason:
            text = (
                f"Paramètre non analysé ({parameter.reason}) : aucune explication "
                "ne peut être fournie tant que la donnée reste incomplète ou incertaine."
            )
        else:
            text = NOT_ANALYZED_PARAMETER_MESSAGE

        return ParameterExplanation(
            code=parameter.code,
            status=ExplanationStatus.not_analyzed,
            text=text,
            source_ids=[],
        )

    return ParameterExplanation(
        code=parameter.code,
        status=ExplanationStatus.insufficient_sources,
        text=INSUFFICIENT_SOURCES_PARAMETER_MESSAGE,
        source_ids=[],
    )


class InsufficientSourcesGenerator:
    """Implémentation de repli utilisée en l'absence de base documentaire exploitable."""

    def generate(self, request: GenerationRequest) -> GenerationResult:
        explanations = [
            build_unavailable_explanation(parameter)
            for parameter in request.parameters
        ]
        return GenerationResult(
            summary=INSUFFICIENT_SOURCES_SUMMARY,
            parameter_explanations=explanations,
            sources=[],
            disclaimer=DISCLAIMER,
        )