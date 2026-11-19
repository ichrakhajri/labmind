"""Générateur d'explications pédagogiques par RAG et LLM local.

Contraintes strictes :
- Aucun diagnostic, aucune prescription, aucune formulation codée en dur.
- Uniquement basé sur les passages documentaires fournis dans `GenerationRequest`.
- Chaque réponse documentaire est vérifiée par `check_explanation_grounding`
  ou `check_lifestyle_grounding`.
- Les questions de consultation sont générées dynamiquement par le LLM local
  puis filtrées par `sanitize_consultation_questions` (ou `[]` en cas d'échec).
"""
from __future__ import annotations

import json
import re

from app.schemas import DISCLAIMER, ParameterResult, ParameterStatus, Source

from .fallback import (
    INSUFFICIENT_SOURCES_SUMMARY,
    InsufficientSourcesGenerator,
    build_unavailable_explanation,
    build_unavailable_lifestyle_info,
)
from .grounding import (
    check_explanation_grounding,
    check_lifestyle_grounding,
    sanitize_consultation_questions,
)
from .interface import (
    ExplanationStatus,
    GenerationRequest,
    GenerationResult,
    LifestyleInfo,
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
    "5. N'invente aucun chiffre ou seuil absent des extraits fournis.\n"
    "6. Si les extraits fournis ne suffisent pas à expliquer le paramètre de façon "
    'fiable et neutre, retourne status="insufficient_sources" et source_ids=[].'
)

LIFESTYLE_SYSTEM_PROMPT = (
    "Tu es un assistant d'information de santé publique pédagogique pour LabMind.\n"
    "Règles absolues :\n"
    "1. Réponds uniquement en JSON valide avec les clés : "
    '"status" ("grounded" ou "insufficient_sources"), "text" (chaîne), '
    '"source_ids" (liste de chaînes).\n'
    "2. Synthétise uniquement les repères généraux d'hygiène de vie présents "
    "dans les extraits documentaires officiels fournis.\n"
    "3. Cite dans source_ids uniquement les identifiants exacts des extraits utilisés.\n"
    "4. Ne pose jamais de diagnostic et ne recommande jamais de médicament, "
    "traitement ou dose.\n"
    "5. N'invente aucun chiffre ni aucune information absente des extraits fournis.\n"
    "6. Si les extraits fournis ne suffisent pas à produire une synthèse fidèle "
    'et neutre, retourne status="insufficient_sources" et source_ids=[].'
)

QUESTIONS_SYSTEM_PROMPT = (
    "Tu es un assistant pédagogique pour LabMind qui aide un patient à préparer "
    "sa consultation médicale.\n"
    "Règles absolues :\n"
    "1. Réponds uniquement en JSON valide avec la clé "
    '"questions" (liste de 2 à 4 courtes questions en français se terminant par \'?\').\n'
    "2. Chaque question doit être formulée de manière neutre pour être posée au médecin "
    "à propos des résultats extraits (signification, contexte clinique, suivi ou "
    "facteurs pouvant influencer la mesure).\n"
    "3. Ne pose aucun diagnostic, ne suggère aucun médicament, traitement ou dose, "
    "et n'affirme pas qu'une maladie est présente.\n"
    "4. N'invente pas de valeurs biologiques absentes des données fournies."
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


def build_lifestyle_prompt(
    parameters: list[ParameterResult],
    lifestyle_passages: list[RetrievedPassage],
) -> str:
    """Construit le prompt utilisateur pour la synthèse documentée d'hygiène de vie."""
    lines = ["Contexte des paramètres extraits (pour cibler les thèmes pertinents) :"]
    if parameters:
        for param in parameters:
            lines.append(
                f"- {param.name_printed} ({param.code}) : {_describe_position(param)}"
            )
    else:
        lines.append("- Bilan biologique général")

    lines.append("")
    lines.append(
        "Extraits officiels d'hygiène de vie autorisés (cite uniquement leurs source_id) :"
    )
    for idx, passage in enumerate(lifestyle_passages, start=1):
        lines.append(
            f"[{idx}] source_id={passage.source.source_id} | "
            f"organisme={passage.source.organisme} | titre={passage.source.title}\n"
            f"Extrait : {passage.excerpt}"
        )

    return "\n".join(lines)


def build_questions_prompt(
    parameters: list[ParameterResult],
    passages: list[RetrievedPassage],
) -> str:
    """Construit le prompt pour générer des questions neutres de consultation médicale."""
    lines = ["Résultats biologiques extraits du document :"]
    for param in parameters:
        ref = param.reference
        ref_str = (
            f"{ref.min} - {ref.max}"
            if ref.min is not None and ref.max is not None
            else "non fournie"
        )
        val_str = (
            f"{param.value} {param.unit or ''}".strip()
            if param.value is not None
            else "absente"
        )
        lines.append(
            f"- {param.name_printed} ({param.code}) : {val_str} "
            f"(réf. : {ref_str} ; position : {_describe_position(param)})"
        )

    if passages:
        lines.append("")
        lines.append("Repères documentaires associés :")
        for idx, passage in enumerate(passages[:3], start=1):
            lines.append(f"[{idx}] {passage.source.organisme} : {passage.excerpt}")

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


def parse_llm_lifestyle(
    raw_response: str,
    allowed_source_ids: set[str],
) -> LifestyleInfo:
    """Valide strictement la réponse du LLM pour la section d'hygiène de vie."""
    payload = _extract_json_object(raw_response)
    if payload is None:
        return build_unavailable_lifestyle_info()

    raw_status = payload.get("status")
    raw_text = payload.get("text")
    raw_source_ids = payload.get("source_ids")

    if raw_status != ExplanationStatus.grounded.value:
        return build_unavailable_lifestyle_info()

    if not isinstance(raw_text, str) or not raw_text.strip():
        return build_unavailable_lifestyle_info()

    if not isinstance(raw_source_ids, list):
        return build_unavailable_lifestyle_info()

    valid_ids: list[str] = []
    for item in raw_source_ids:
        if isinstance(item, str) and item in allowed_source_ids and item not in valid_ids:
            valid_ids.append(item)

    if not valid_ids:
        return build_unavailable_lifestyle_info()

    return LifestyleInfo(
        status=ExplanationStatus.grounded,
        text=raw_text.strip(),
        source_ids=valid_ids,
    )


def parse_llm_questions(
    raw_response: str,
    max_questions: int = 4,
) -> list[str]:
    """Extrait et filtre la liste de questions proposée par le LLM."""
    payload = _extract_json_object(raw_response)
    if payload is None:
        return []

    raw_questions = payload.get("questions")
    if not isinstance(raw_questions, list):
        return []

    return sanitize_consultation_questions(raw_questions, max_questions=max_questions)


class RagExplanationGenerator:
    """Générateur RAG avec vérification d'ancrage et reformulation prudente."""

    def __init__(
        self,
        llm_client: LocalLLMClient,
        system_prompt: str = SYSTEM_PROMPT,
        lifestyle_system_prompt: str = LIFESTYLE_SYSTEM_PROMPT,
        questions_system_prompt: str = QUESTIONS_SYSTEM_PROMPT,
        min_overlap_ratio: float = 0.25,
        max_retries: int = 1,
    ) -> None:
        self.llm_client = llm_client
        self.system_prompt = system_prompt
        self.lifestyle_system_prompt = lifestyle_system_prompt
        self.questions_system_prompt = questions_system_prompt
        self.min_overlap_ratio = min_overlap_ratio
        self.max_retries = max(0, max_retries)
        self._fallback = InsufficientSourcesGenerator()

    def _generate_for_parameter(
        self,
        parameter: ParameterResult,
        passages: list[RetrievedPassage],
        allowed_ids: set[str],
    ) -> ParameterExplanation:
        base_prompt = build_parameter_prompt(parameter, passages)
        prompt = base_prompt

        for attempt in range(self.max_retries + 1):
            try:
                raw_response = self.llm_client.generate(self.system_prompt, prompt)
            except LocalLLMError:
                return build_unavailable_explanation(parameter)

            explanation = parse_llm_explanation(parameter, raw_response, allowed_ids)
            if explanation.status != ExplanationStatus.grounded:
                return explanation

            check = check_explanation_grounding(
                explanation=explanation,
                parameter=parameter,
                passages=passages,
                min_overlap_ratio=self.min_overlap_ratio,
            )
            if check.is_grounded:
                return explanation

            if attempt < self.max_retries:
                reasons_text = " ; ".join(check.reasons)
                prompt = (
                    f"{base_prompt}\n\n"
                    f"CORRECTION OBLIGATOIRE : ta tentative précédente a été rejetée "
                    f"({reasons_text}). Reformule uniquement avec les faits et termes "
                    f"présents dans les extraits fournis, sans chiffre non sourcé, ou "
                    f'retourne status="insufficient_sources" et source_ids=[].'
                )

        return build_unavailable_explanation(parameter)

    def _generate_lifestyle_info(
        self,
        parameters: list[ParameterResult],
        lifestyle_passages: list[RetrievedPassage],
    ) -> LifestyleInfo:
        allowed_ids = {passage.source.source_id for passage in lifestyle_passages}
        base_prompt = build_lifestyle_prompt(parameters, lifestyle_passages)
        prompt = base_prompt

        for attempt in range(self.max_retries + 1):
            try:
                raw_response = self.llm_client.generate(
                    self.lifestyle_system_prompt,
                    prompt,
                )
            except LocalLLMError:
                return build_unavailable_lifestyle_info()

            lifestyle_info = parse_llm_lifestyle(raw_response, allowed_ids)
            if lifestyle_info.status != ExplanationStatus.grounded:
                return lifestyle_info

            check = check_lifestyle_grounding(
                lifestyle_info=lifestyle_info,
                lifestyle_passages=lifestyle_passages,
                parameters=parameters,
                min_overlap_ratio=self.min_overlap_ratio,
            )
            if check.is_grounded:
                return lifestyle_info

            if attempt < self.max_retries:
                reasons_text = " ; ".join(check.reasons)
                prompt = (
                    f"{base_prompt}\n\n"
                    f"CORRECTION OBLIGATOIRE : ta tentative précédente a été rejetée "
                    f"({reasons_text}). Reformule uniquement avec les faits et termes "
                    f"présents dans les extraits fournis, sans chiffre non sourcé, ou "
                    f'retourne status="insufficient_sources" et source_ids=[].'
                )

        return build_unavailable_lifestyle_info()

    def _generate_consultation_questions(
        self,
        parameters: list[ParameterResult],
        passages: list[RetrievedPassage],
    ) -> list[str]:
        active_parameters = [
            param
            for param in parameters
            if param.status != ParameterStatus.not_analyzed
        ]
        if not active_parameters:
            return []

        prompt = build_questions_prompt(active_parameters, passages)
        try:
            raw_response = self.llm_client.generate(
                self.questions_system_prompt,
                prompt,
            )
        except LocalLLMError:
            return []

        return parse_llm_questions(raw_response)

    def generate(self, request: GenerationRequest) -> GenerationResult:
        if not request.parameters and not request.lifestyle_passages:
            return self._fallback.generate(request)

        if not request.passages and not request.lifestyle_passages:
            return self._fallback.generate(request)

        sources_by_id: dict[str, Source] = {
            passage.source.source_id: passage.source
            for passage in (*request.passages, *request.lifestyle_passages)
        }
        allowed_param_ids = {
            passage.source.source_id for passage in request.passages
        }

        explanations: list[ParameterExplanation] = []
        used_sources: dict[str, Source] = {}

        for parameter in request.parameters:
            if parameter.status == ParameterStatus.not_analyzed or not request.passages:
                explanations.append(build_unavailable_explanation(parameter))
                continue

            explanation = self._generate_for_parameter(
                parameter, request.passages, allowed_param_ids
            )
            explanations.append(explanation)

            for sid in explanation.source_ids:
                if sid not in used_sources:
                    used_sources[sid] = sources_by_id[sid]

        if request.lifestyle_passages:
            lifestyle_info: LifestyleInfo | None = self._generate_lifestyle_info(
                request.parameters, request.lifestyle_passages
            )
            for sid in lifestyle_info.source_ids:
                if sid not in used_sources:
                    used_sources[sid] = sources_by_id[sid]
        elif request.include_consultation_questions:
            lifestyle_info = build_unavailable_lifestyle_info()
        else:
            lifestyle_info = None

        consultation_questions = (
            self._generate_consultation_questions(request.parameters, request.passages)
            if request.include_consultation_questions
            else []
        )

        has_grounded = any(
            item.status == ExplanationStatus.grounded for item in explanations
        ) or (
            lifestyle_info is not None
            and lifestyle_info.status == ExplanationStatus.grounded
        )
        summary = GROUNDED_SUMMARY if has_grounded else INSUFFICIENT_SOURCES_SUMMARY

        return GenerationResult(
            summary=summary,
            parameter_explanations=explanations,
            lifestyle_info=lifestyle_info,
            consultation_questions=consultation_questions,
            sources=list(used_sources.values()),
            disclaimer=DISCLAIMER,
        )