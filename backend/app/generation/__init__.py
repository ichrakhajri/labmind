"""Module de génération d'explications pédagogiques sourcées."""

from .interface import (
    ExplanationGenerator,
    ExplanationStatus,
    GenerationRequest,
    GenerationResult,
    ParameterExplanation,
    RetrievedPassage,
    find_citation_errors,
)

__all__ = [
    "ExplanationGenerator",
    "ExplanationStatus",
    "GenerationRequest",
    "GenerationResult",
    "ParameterExplanation",
    "RetrievedPassage",
    "find_citation_errors",
]