"""Point d'entrée de l'API LabMind pour uvicorn (`uvicorn app.main:app`)."""
from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Callable

from fastapi import FastAPI

from app.agent import AgentOrchestrator
from app.core.config import PROJECT_DIR, Settings, get_settings
from app.generation import RagExplanationGenerator
from app.generation.llm_client import LocalLLMClient, OllamaLLMClient
from app.knowledge.retriever import (
    FaissKnowledgeIndex,
    SentenceTransformerEmbedder,
    TextEmbedder,
)

from .api.app import create_app
from .api.store import TaskManager

logger = logging.getLogger("labmind.startup")

DEFAULT_INDEX_DIR = PROJECT_DIR / "knowledge_corpus" / "processed"


def _env_flag(name: str, default: bool = True) -> bool:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


def _load_knowledge_index(
    index_dir: Path,
    embedder: TextEmbedder | None = None,
) -> FaissKnowledgeIndex | None:
    passages_file = index_dir / FaissKnowledgeIndex.PASSAGES_FILENAME
    faiss_file = index_dir / FaissKnowledgeIndex.INDEX_FILENAME
    if not passages_file.is_file() or not faiss_file.is_file():
        logger.info("Index FAISS absent dans %s : mode repli neutre actif.", index_dir)
        return None

    try:
        active_embedder = embedder or SentenceTransformerEmbedder()
        index = FaissKnowledgeIndex.load(index_dir, active_embedder)
        logger.info("Index FAISS chargé (%d passages).", len(index.passages))
        return index
    except Exception:
        logger.warning("Chargement de l'index FAISS impossible : bascule en mode repli neutre.")
        return None


def build_orchestrator_factory(
    enable_rag: bool = True,
    index_dir: Path = DEFAULT_INDEX_DIR,
    embedder: TextEmbedder | None = None,
    llm_client: LocalLLMClient | None = None,
) -> Callable[[], AgentOrchestrator]:
    """Construit la fabrique d'AgentOrchestrator pour l'API."""
    knowledge_index = _load_knowledge_index(index_dir, embedder=embedder) if enable_rag else None
    generator = (
        RagExplanationGenerator(llm_client=llm_client or OllamaLLMClient())
        if knowledge_index is not None
        else None
    )

    def _factory() -> AgentOrchestrator:
        return AgentOrchestrator(
            knowledge_index=knowledge_index,
            generator=generator,
        )

    return _factory


def create_runtime_app(
    settings: Settings | None = None,
    enable_rag: bool | None = None,
    index_dir: Path = DEFAULT_INDEX_DIR,
) -> FastAPI:
    """Crée l'application FastAPI avec purge au démarrage et RAG optionnel."""
    active_settings = settings or get_settings()
    use_rag = _env_flag("LABMIND_ENABLE_RAG", True) if enable_rag is None else enable_rag

    @asynccontextmanager
    async def lifespan(fastapi_app: FastAPI):
        if use_rag:
            factory = build_orchestrator_factory(
                enable_rag=True,
                index_dir=index_dir,
            )
            fastapi_app.state.task_manager.close()
            fastapi_app.state.task_manager = TaskManager(
                settings=active_settings,
                orchestrator_factory=factory,
            )
        fastapi_app.state.task_manager.purge_expired()
        try:
            yield
        finally:
            fastapi_app.state.task_manager.close()

    fastapi_app = create_app(settings=active_settings)
    fastapi_app.router.lifespan_context = lifespan
    return fastapi_app


app = create_runtime_app()