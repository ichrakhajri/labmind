"""Générateur d'explications pédagogiques par RAG et LLM local.

Contraintes strictes :
- Aucun diagnostic, aucune prescription, aucune recommandation codée en dur.
- Uniquement basé sur les passages documentaires fournis dans `GenerationRequest`.
- Toute citation inventée ou réponse invalide déclenche un repli neutre.
"""
from __future__ import annotations

import json
import re

from app.schemas import DISCLAIMER, ParameterResult, ParameterStatus, Source

from .fallback import (
    INSUFFICIENT_SOURCES_SUMMARY,
    InsufficientSourcesGenerator,
    build_unavailable_explanation,
)
from .interface import (
    ExplanationStatus,
    GenerationRequest,
    GenerationResult,
    ParameterExplanation,
    RetrievedPassage,
)
from .llm_client import LocalLLMClient, LocalLLMError

SYSTEM_PROMPT = (
    "Tu es un assistant d'information biologique pédagogique pour LabMind.\n"
    "Règles absolues :\n"
    "1. Réponds uniquement en JSON valide avec les clés : "
    '"status" ("grounded" ou "insufficient_sources"), "text" (chaîne), '
    '"source_ids" (liste de chaînes).\n'
    "2. Appuie chaque phrase exclusivement sur les extraits documentaires fournis.\n"
    "3. Cite dans source_ids uniquement les identifiants exacts des extraits utilisés.\n"
    "4. Ne pose jamais de diagnostic et ne recommande jamais de médicament, "
    "traitement ou dose.\n"
    "5. Si les extraits fournis ne suffisent pas à expliquer le paramètre de façon "
    'fiable et neutre, retourne status="insufficient_sources" et source_ids=[].'
)

GROUNDED_SUMMARY = (
    "Explications pédagogiques produites exclusivement à partir des sources "
    "documentaires vérifiées."
)


def _describe_position(parameter: ParameterResult) -> str:
    """Décrit de façon purement arithmétique la position par rapport à la fourchette."""
    if parameter.status == ParameterStatus.below_reference:
        return "inférieure à l'intervalle du laboratoire"
    if parameter.status == ParameterStatus.within_reference:
        return "dans l'intervalle du laboratoire"
    if parameter.status == ParameterStatus.above_reference:
        return "supérieure à l'intervalle du laboratoire"
    if parameter.status == ParameterStatus.reference_unavailable:
        return "intervalle de référence non disponible sur le document"
    if parameter.status == ParameterStatus.value_unavailable:
        return "valeur numérique non disponible"
    return "non analysé"


def build_parameter_prompt(
    parameter: ParameterResult,
    passages: list[RetrievedPassage],
) -> str:
    """Construit le prompt utilisateur pour un paramètre et des passages donnés."""
    ref = parameter.reference
    if ref.min is not None and ref.max is not None:
        ref_str = f"{ref.min} - {ref.max}"
    else:
        ref_str = "non fournie"

    val_str = (
        f"{parameter.value} {parameter.unit or ''}".strip()
        if parameter.value is not None
        else "absente"
    )

    lines = [
        "Paramètre biologique à expliquer :",
        f"- Code : {parameter.code}",
        f"- Nom imprimé : {parameter.name_printed}",
        f"- Valeur extraite : {val_str}",
        f"- Fourchette du laboratoire : {ref_str}",
        f"- Position arithmétique : {_describe_position(parameter)}",
        "",
        "Extraits documentaires autorisés (cite uniquement leurs source_id) :",
    ]

    for idx, passage in enumerate(passages, start=1):
        lines.append(
            f"[{idx}] source_id={passage.source.source_id} | "
            f"organisme={passage.source.organisme} | titre={passage.source.title}\n"
            f"Extrait : {passage.excerpt}"
        )

    return "\n".join(lines)


def _extract_json_object(raw_text: str) -> dict | None:
    """Extrait un objet JSON même si le modèle ajoute des balises Markdown."""
    cleaned = raw_text.strip()
    fenced = re.search(r"```(?:json)?\s*(\{.*\})\s*```", cleaned, flags=re.DOTALL)
    if fenced:
        cleaned = fenced.group(1)
    else:
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start != -1 and end > start:
            cleaned = cleaned[start : end + 1]

    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def parse_llm_explanation(
    parameter: ParameterResult,
    raw_response: str,
    allowed_source_ids: set[str],
) -> ParameterExplanation:
    """Valide strictement la réponse du LLM ou bascule vers un repli neutre."""
    payload = _extract_json_object(raw_response)
    if payload is None:
        return build_unavailable_explanation(parameter)

    raw_status = payload.get("status")
    raw_text = payload.get("text")
    raw_source_ids = payload.get("source_ids")

    if raw_status != ExplanationStatus.grounded.value:
        return build_unavailable_explanation(parameter)

    if not isinstance(raw_text, str) or not raw_text.strip():
        return build_unavailable_explanation(parameter)

    if not isinstance(raw_source_ids, list):
        return build_unavailable_explanation(parameter)

    # Garde uniquement les source_id connus dans les passages fournis (sans doublons)
    valid_ids: list[str] = []
    for item in raw_source_ids:
        if isinstance(item, str) and item in allowed_source_ids and item not in valid_ids:
            valid_ids.append(item)

    if not valid_ids:
        return build_unavailable_explanation(parameter)

    return ParameterExplanation(
        code=parameter.code,
        status=ExplanationStatus.grounded,
        text=raw_text.strip(),
        source_ids=valid_ids,
    )


class RagExplanationGenerator:
    """Générateur RAG implémentant le protocole `ExplanationGenerator`."""

    def __init__(
        self,
        llm_client: LocalLLMClient,
        system_prompt: str = SYSTEM_PROMPT,
    ) -> None:
        self.llm_client = llm_client
        self.system_prompt = system_prompt
        self._fallback = InsufficientSourcesGenerator()

    def generate(self, request: GenerationRequest) -> GenerationResult:
        if not request.parameters or not request.passages:
            return self._fallback.generate(request)

        sources_by_id: dict[str, Source] = {
            passage.source.source_id: passage.source
            for passage in request.passages
        }
        allowed_ids = set(sources_by_id.keys())

        explanations: list[ParameterExplanation] = []
        used_sources: dict[str, Source] = {}

        for parameter in request.parameters:
            if parameter.status == ParameterStatus.not_analyzed:
                explanations.append(build_unavailable_explanation(parameter))
                continue

            prompt = build_parameter_prompt(parameter, request.passages)
            try:
                raw_response = self.llm_client.generate(self.system_prompt, prompt)
            except LocalLLMError:
                explanations.append(build_unavailable_explanation(parameter))
                continue

            explanation = parse_llm_explanation(parameter, raw_response, allowed_ids)
            explanations.append(explanation)

            for sid in explanation.source_ids:
                if sid not in used_sources:
                    used_sources[sid] = sources_by_id[sid]

        has_grounded = any(
            item.status == ExplanationStatus.grounded for item in explanations
        )
        summary = GROUNDED_SUMMARY if has_grounded else INSUFFICIENT_SOURCES_SUMMARY

        return GenerationResult(
            summary=summary,
            parameter_explanations=explanations,
            sources=list(used_sources.values()),
            disclaimer=DISCLAIMER,
        )