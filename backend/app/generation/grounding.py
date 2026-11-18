"""Contrôle d'ancrage (grounding check) et de prudence sur les explications générées.

Vérifie qu'une explication marquée 'grounded' :
1. ne contient aucune formulation de diagnostic ou de prescription ;
2. n'introduit aucun chiffre absent du paramètre et des passages cités ;
3. recouvre lexicalement les extraits documentaires cités.
"""
from __future__ import annotations

import re
import unicodedata

from pydantic import BaseModel, Field

from app.schemas import ParameterResult

from .interface import ExplanationStatus, ParameterExplanation, RetrievedPassage

SAFETY_FORBIDDEN_PATTERNS = (
    r"\bvous\s+(?:souffrez|êtes\s+atteint)\b",
    r"\bvous\s+avez\s+(?:une?\s+)?(?:maladie|pathologie|anémie|diabète|insuffisance)\b",
    r"\bdiagnostic\s+(?:confirmé|positif|établi|certain)\b",
    r"\bje\s+vous\s+(?:prescris|diagnostique)\b",
    r"\btraitement\s+(?:recommandé|à\s+suivre|médicamenteux)\b",
    r"\bdébuter\s+un\s+traitement\b",
    r"\bmodifier\s+votre\s+traitement\b",
    r"\bdose\s+quotidienne\b",
)

_STOPWORDS = {
    "avec",
    "ainsi",
    "alors",
    "aussi",
    "autre",
    "autres",
    "avant",
    "avoir",
    "bien",
    "cette",
    "chez",
    "comme",
    "dans",
    "depuis",
    "donc",
    "dont",
    "elle",
    "elles",
    "entre",
    "etre",
    "fait",
    "faut",
    "hors",
    "intervalle",
    "laboratoire",
    "leur",
    "leurs",
    "mais",
    "meme",
    "moins",
    "nous",
    "parametre",
    "parce",
    "parmi",
    "peut",
    "peuvent",
    "plus",
    "pour",
    "quand",
    "quel",
    "quelle",
    "quelles",
    "quels",
    "reference",
    "sans",
    "selon",
    "sera",
    "seront",
    "sont",
    "sous",
    "tous",
    "tout",
    "toute",
    "toutes",
    "tres",
    "unite",
    "valeur",
    "valeurs",
    "vers",
    "vous",
}


class GroundingCheckResult(BaseModel):
    """Résultat détaillé du contrôle d'ancrage d'une explication."""

    is_grounded: bool
    overlap_ratio: float
    ungrounded_numbers: list[str] = Field(default_factory=list)
    safety_violations: list[str] = Field(default_factory=list)
    reasons: list[str] = Field(default_factory=list)


def _strip_accents(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch))


def _content_tokens(text: str) -> set[str]:
    normalized = _strip_accents(text.lower())
    tokens = set(re.findall(r"[a-z]{4,}", normalized))
    return {tok for tok in tokens if tok not in _STOPWORDS}


def _extract_numbers(text: str) -> set[str]:
    raw_nums = re.findall(r"\b\d+(?:[.,]\d+)?\b", text)
    normalized: set[str] = set()
    for item in raw_nums:
        val_str = item.replace(",", ".")
        try:
            num = float(val_str)
            normalized.add(f"{num:g}")
        except ValueError:
            normalized.add(val_str)
    return normalized


def _allowed_numbers_for(
    parameter: ParameterResult,
    cited_passages: list[RetrievedPassage],
) -> set[str]:
    allowed: set[str] = set()
    for num in (parameter.value, parameter.reference.min, parameter.reference.max):
        if num is not None:
            allowed.add(f"{float(num):g}")

    for passage in cited_passages:
        allowed.update(_extract_numbers(passage.excerpt))
        allowed.update(_extract_numbers(passage.source.source_id))
        if passage.source.date:
            allowed.update(_extract_numbers(passage.source.date))
    return allowed


def check_safety_compliance(text: str) -> list[str]:
    """Vérifie l'absence de formulation de diagnostic ou de traitement."""
    lowered = text.lower()
    violations: list[str] = []
    for pattern in SAFETY_FORBIDDEN_PATTERNS:
        if re.search(pattern, lowered, flags=re.IGNORECASE):
            violations.append(pattern)
    return violations


def check_explanation_grounding(
    explanation: ParameterExplanation,
    parameter: ParameterResult,
    passages: list[RetrievedPassage],
    min_overlap_ratio: float = 0.25,
) -> GroundingCheckResult:
    """Vérifie qu'une explication est sûre et ancrée dans ses passages cités."""
    if explanation.status != ExplanationStatus.grounded:
        return GroundingCheckResult(
            is_grounded=False,
            overlap_ratio=0.0,
            reasons=["L'explication n'est pas au statut 'grounded'."],
        )

    passages_by_sid: dict[str, list[RetrievedPassage]] = {}
    for passage in passages:
        passages_by_sid.setdefault(passage.source.source_id, []).append(passage)

    cited_passages: list[RetrievedPassage] = []
    for sid in explanation.source_ids:
        cited_passages.extend(passages_by_sid.get(sid, []))

    if not cited_passages:
        return GroundingCheckResult(
            is_grounded=False,
            overlap_ratio=0.0,
            reasons=["Aucun passage correspondant aux source_ids cités."],
        )

    reasons: list[str] = []
    safety_violations = check_safety_compliance(explanation.text)
    if safety_violations:
        reasons.append("Formulation non conforme aux règles de prudence détectée.")

    allowed_nums = _allowed_numbers_for(parameter, cited_passages)
    found_nums = _extract_numbers(explanation.text)
    ungrounded_numbers = sorted(found_nums - allowed_nums)
    if ungrounded_numbers:
        reasons.append(
            f"Nombres non présents dans les passages ou le bilan : {', '.join(ungrounded_numbers)}."
        )

    # Ignore l'identifiant technique du source_id cité lors du calcul lexical
    text_for_tokens = explanation.text
    for sid in explanation.source_ids:
        text_for_tokens = text_for_tokens.replace(sid, " ")

    explanation_tokens = _content_tokens(text_for_tokens)
    passage_tokens: set[str] = set()
    for passage in cited_passages:
        passage_tokens.update(_content_tokens(passage.excerpt))

    if not explanation_tokens:
        overlap_ratio = 0.0
        reasons.append("Explication trop pauvre en termes vérifiables.")
    else:
        overlap_ratio = len(explanation_tokens & passage_tokens) / len(explanation_tokens)
        if overlap_ratio < min_overlap_ratio:
            reasons.append(
                f"Recouvrement lexical insuffisant ({overlap_ratio:.2f} < {min_overlap_ratio:.2f})."
            )

    return GroundingCheckResult(
        is_grounded=len(reasons) == 0,
        overlap_ratio=round(overlap_ratio, 4),
        ungrounded_numbers=ungrounded_numbers,
        safety_violations=safety_violations,
        reasons=reasons,
    )