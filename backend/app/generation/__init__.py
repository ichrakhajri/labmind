"""Module de génération d'explications pédagogiques sourcées."""

from .fallback import (
    INSUFFICIENT_SOURCES_PARAMETER_MESSAGE,
    INSUFFICIENT_SOURCES_SUMMARY,
    NOT_ANALYZED_PARAMETER_MESSAGE,
    InsufficientSourcesGenerator,
    build_unavailable_explanation,
)
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
    "INSUFFICIENT_SOURCES_PARAMETER_MESSAGE",
    "INSUFFICIENT_SOURCES_SUMMARY",
    "InsufficientSourcesGenerator",
    "NOT_ANALYZED_PARAMETER_MESSAGE",
    "ParameterExplanation",
    "RetrievedPassage",
    "build_unavailable_explanation",
    "find_citation_errors",
]