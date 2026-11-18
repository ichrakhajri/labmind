"""Outils indépendants exécutables par l'agent LabMind."""
from __future__ import annotations

from pathlib import Path
from typing import Callable

import pdfplumber
from pydantic import BaseModel

from app.extraction.extractor import extract_document
from app.generation import (
    ExplanationGenerator,
    GenerationRequest,
    InsufficientSourcesGenerator,
)
from app.generation.interface import RetrievedPassage
from app.identification.catalog import ACCEPTED_UNITS
from app.identification.parser import identify_parameters
from app.knowledge.retriever import FaissKnowledgeIndex
from app.schemas import (
    ExtractionMethod,
    ParameterStatus,
    PendingQuestion,
    TaskStatus,
    parameter_from_dict,
)
from app.validation.analysis import analyze_parameters

from .state import AgentState, UncertaintyItem

MIN_NATIVE_PDF_CHARS = 30
SKIP_ANSWER_LABEL = "je ne sais pas"


class ToolExecutionResult(BaseModel):
    """Compte rendu retourné après exécution d'un outil."""

    success: bool
    summary: str


def _default_pdf_text_reader(path: Path) -> str:
    with pdfplumber.open(path) as pdf:
        pages_text = [page.extract_text() or "" for page in pdf.pages]
    return "\n".join(pages_text).strip()


def run_extract_pdf_text(
    state: AgentState,
    pdf_reader: Callable[[Path], str] | None = None,
) -> ToolExecutionResult:
    """Tente uniquement une lecture texte natif sur un fichier PDF."""
    state.tried_pdf_text = True
    path = Path(state.file_path)

    if path.suffix.lower() != ".pdf":
        return ToolExecutionResult(
            success=False,
            summary="Le fichier n'est pas un PDF natif : une lecture OCR est requise.",
        )

    reader = pdf_reader or _default_pdf_text_reader
    try:
        text = reader(path).strip()
    except Exception as exc:
        return ToolExecutionResult(
            success=False,
            summary=f"Échec de lecture texte natif PDF : {exc}",
        )

    if len(text) < MIN_NATIVE_PDF_CHARS:
        state.raw_text = ""
        return ToolExecutionResult(
            success=False,
            summary="PDF sans couche texte exploitable (probable scan) : bascule OCR nécessaire.",
        )

    state.raw_text = text
    state.extraction_method = ExtractionMethod.pdf_text
    return ToolExecutionResult(
        success=True,
        summary=f"Texte natif PDF extrait ({len(text)} caractères).",
    )


def run_extract_ocr(
    state: AgentState,
    ocr_reader: Callable[[Path], dict] | None = None,
) -> ToolExecutionResult:
    """Exécute l'extraction par OCR (ou extract_document) sur image ou PDF scanné."""
    state.tried_ocr = True
    path = Path(state.file_path)
    reader = ocr_reader or extract_document

    try:
        result = reader(path)
    except Exception as exc:
        return ToolExecutionResult(
            success=False,
            summary=f"Échec de l'extraction OCR : {exc}",
        )

    text = str(result.get("text", "")).strip()
    if not text:
        return ToolExecutionResult(
            success=False,
            summary="Aucun texte exploitable obtenu après OCR.",
        )

    state.raw_text = text
    state.extraction_method = ExtractionMethod.ocr
    return ToolExecutionResult(
        success=True,
        summary=f"Texte OCR extrait ({len(text)} caractères).",
    )


def _build_uncertainties(analyzed: list[dict]) -> list[UncertaintyItem]:
    """Identifie les paramètres ambigus pouvant faire l'objet d'une confirmation."""
    items: list[UncertaintyItem] = []
    for raw in analyzed:
        if raw.get("status") != ParameterStatus.not_analyzed.value:
            continue

        code = raw["code"]
        name_printed = raw.get("name_printed") or code
        reason_code = raw.get("reason_code") or ""

        if reason_code in ("missing_unit", "unexpected_unit"):
            accepted = list(ACCEPTED_UNITS.get(code, ()))
            options = accepted + ["autre", SKIP_ANSWER_LABEL]
            items.append(
                UncertaintyItem(
                    code=code,
                    name_printed=name_printed,
                    field="unit",
                    reason_code=reason_code,
                    options=options,
                )
            )
        elif reason_code in ("missing_value", "implausible"):
            items.append(
                UncertaintyItem(
                    code=code,
                    name_printed=name_printed,
                    field="value",
                    reason_code=reason_code,
                    options=[SKIP_ANSWER_LABEL],
                )
            )

    return items


def run_identify_and_validate(state: AgentState) -> ToolExecutionResult:
    """Identifie les paramètres depuis `raw_text`, les valide techniquement et repère les incertitudes."""
    if not state.raw_text.strip():
        return ToolExecutionResult(
            success=False,
            summary="Impossible d'identifier les paramètres : aucun texte extrait.",
        )

    method_value = (
        state.extraction_method.value
        if state.extraction_method is not None
        else ExtractionMethod.pdf_text.value
    )

    identified = identify_parameters(state.raw_text)
    analyzed = analyze_parameters(identified, method=method_value)

    state.raw_parameters = analyzed
    state.validated_parameters = [parameter_from_dict(item) for item in analyzed]
    state.uncertainties = _build_uncertainties(analyzed)

    unresolved_count = len(state.uncertainties)
    return ToolExecutionResult(
        success=True,
        summary=(
            f"{len(state.validated_parameters)} paramètre(s) analysé(s), "
            f"{unresolved_count} incertitude(s) détectée(s)."
        ),
    )


def run_request_user_confirmation(state: AgentState) -> ToolExecutionResult:
    """Prépare une question unique (API v1) pour la prochaine incertitude non résolue."""
    unresolved = state.unresolved_uncertainties()
    if not unresolved:
        return ToolExecutionResult(
            success=False,
            summary="Aucune incertitude en attente de confirmation.",
        )

    target = unresolved[0]
    state.question_counter += 1
    question_id = f"q-{state.question_counter:03d}"

    if target.field == "unit":
        message = (
            f"L'unité du paramètre {target.name_printed} ({target.code}) est absente "
            "ou illisible. Quelle unité figure sur votre document ?"
        )
    else:
        message = (
            f"La valeur du paramètre {target.name_printed} ({target.code}) semble "
            "incertaine après lecture. Quelle valeur numérique figure sur votre document ?"
        )

    options = list(target.options)
    if SKIP_ANSWER_LABEL not in options:
        options.append(SKIP_ANSWER_LABEL)

    state.pending_question = PendingQuestion(
        question_id=question_id,
        field=target.field,
        code=target.code,
        message=message,
        options=options,
    )
    state.status = TaskStatus.waiting_for_user
    return ToolExecutionResult(
        success=True,
        summary=f"Question {question_id} posée pour {target.code} ({target.field}).",
    )


def run_retrieve_knowledge(
    state: AgentState,
    knowledge_index: FaissKnowledgeIndex | None = None,
    top_k_per_parameter: int = 2,
) -> ToolExecutionResult:
    """Recherche des passages documentaires ciblés pour chaque paramètre analysable."""
    state.knowledge_searched = True

    if knowledge_index is None:
        state.retrieved_passages = []
        return ToolExecutionResult(
            success=True,
            summary="Aucun index documentaire chargé : 0 passage récupéré.",
        )

    seen_passage_ids: set[str] = set()
    collected: list[RetrievedPassage] = []

    for param in state.validated_parameters:
        if param.status == ParameterStatus.not_analyzed:
            continue

        query = f"{param.name_printed} {param.code} prise de sang"
        found = knowledge_index.search(query=query, top_k=top_k_per_parameter)
        for passage in found:
            if passage.passage_id not in seen_passage_ids:
                seen_passage_ids.add(passage.passage_id)
                collected.append(passage)

    state.retrieved_passages = collected
    return ToolExecutionResult(
        success=True,
        summary=f"{len(collected)} passage(s) documentaire(s) récupéré(s).",
    )


def run_generate_explanations(
    state: AgentState,
    generator: ExplanationGenerator | None = None,
) -> ToolExecutionResult:
    """Produit les explications pédagogiques sourcées (ou repli neutre si sources absentes)."""
    active_generator = generator or InsufficientSourcesGenerator()
    request = GenerationRequest(
        parameters=state.validated_parameters,
        passages=state.retrieved_passages,
    )
    state.generation_result = active_generator.generate(request)

    return ToolExecutionResult(
        success=True,
        summary=(
            f"Génération terminée pour {len(state.generation_result.parameter_explanations)} "
            f"paramètre(s), {len(state.generation_result.sources)} source(s) citée(s)."
        ),
    )