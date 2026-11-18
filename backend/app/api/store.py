"""Gestionnaire de tâches en mémoire reliant l'API à l'AgentOrchestrator."""
from __future__ import annotations

import io
import logging
import threading
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

from app.agent import AgentOrchestrator, AgentState
from app.core.config import Settings
from app.schemas import AnswerIn, Task, TaskStatus

logger = logging.getLogger("labmind.api")


class TaskNotFoundError(Exception):
    """Levée lorsqu'une tâche est inconnue ou déjà supprimée."""


class ReportNotReadyError(Exception):
    """Levée lorsque le téléchargement PDF est demandé avant l'état `done`."""


@dataclass
class TaskRecord:
    """Enregistrement interne d'une tâche en cours ou terminée."""

    state: AgentState
    report_id: str | None = None


def _cleanup_file(file_path: str | Path) -> None:
    try:
        path = Path(file_path)
        if path.is_file():
            path.unlink()
    except OSError:
        logger.warning("Impossible de supprimer un fichier temporaire.")


def _build_placeholder_pdf_bytes(task: Task) -> bytes:
    """Produit un PDF provisoire valide en attendant le générateur complet (Étape 8)."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    styles = getSampleStyleSheet()
    elements = [
        Paragraph("<b>LabMind — Rapport technique provisoire</b>", styles["Title"]),
        Spacer(1, 12),
        Paragraph(f"Identifiant de tâche : {task.task_id}", styles["Normal"]),
        Paragraph(f"Nombre de paramètres : {len(task.parameters)}", styles["Normal"]),
        Spacer(1, 12),
        Paragraph(task.disclaimer, styles["Normal"]),
    ]
    doc.build(elements)
    return buffer.getvalue()


class TaskManager:
    """Stockage thread-safe des tâches (sera persisté en base à l'Étape 7)."""

    def __init__(
        self,
        settings: Settings,
        orchestrator_factory: Callable[[], AgentOrchestrator] | None = None,
        report_builder: Callable[[Task], bytes] | None = None,
    ) -> None:
        self.settings = settings
        self._orchestrator_factory = orchestrator_factory or AgentOrchestrator
        self._report_builder = report_builder or _build_placeholder_pdf_bytes
        self._lock = threading.RLock()
        self._records: dict[str, TaskRecord] = {}

    def create_task(self, original_filename: str, content: bytes) -> Task:
        """Enregistre le fichier sous un nom technique UUID4 et crée la tâche."""
        self.settings.ensure_dirs()
        task_id = str(uuid.uuid4())
        safe_name = Path(original_filename or "document").name
        suffix = Path(safe_name).suffix.lower()
        target_path = self.settings.uploads_dir / f"{task_id}{suffix}"
        target_path.write_bytes(content)

        state = AgentState(
            task_id=task_id,
            file_path=str(target_path),
            filename=safe_name,
            status=TaskStatus.received,
        )
        with self._lock:
            self._records[task_id] = TaskRecord(state=state)
            logger.info("Tâche créée : %s", task_id)
            return state.to_task()

    def process_task(self, task_id: str) -> None:
        """Exécute la boucle agentique sur une tâche reçue."""
        with self._lock:
            record = self._records.get(task_id)
            if record is None:
                return
            state = record.state
            state.status = TaskStatus.processing

        orchestrator = self._orchestrator_factory()
        orchestrator.run(state)

        with self._lock:
            if state.status == TaskStatus.done and record.report_id is None:
                record.report_id = f"r-{task_id[:8]}"
            if state.status in (TaskStatus.done, TaskStatus.error):
                _cleanup_file(state.file_path)
            logger.info("Tâche %s -> statut %s", task_id, state.status.value)

    def get_task(self, task_id: str) -> Task | None:
        """Retourne la vue API `Task` d'une tâche existante, ou None."""
        with self._lock:
            record = self._records.get(task_id)
            if record is None:
                return None
            return record.state.to_task(report_id=record.report_id)

    def answer_task(self, task_id: str, answer_in: AnswerIn) -> Task:
        """Soumet une réponse utilisateur et reprend l'exécution de l'agent."""
        with self._lock:
            record = self._records.get(task_id)
            if record is None:
                raise TaskNotFoundError(task_id)
            state = record.state

        orchestrator = self._orchestrator_factory()
        orchestrator.resume(state, answer_in)

        with self._lock:
            if state.status == TaskStatus.done and record.report_id is None:
                record.report_id = f"r-{task_id[:8]}"
            if state.status in (TaskStatus.done, TaskStatus.error):
                _cleanup_file(state.file_path)
            logger.info("Réponse traitée pour %s -> statut %s", task_id, state.status.value)
            return state.to_task(report_id=record.report_id)

    def get_report_pdf(self, task_id: str) -> tuple[bytes, str]:
        """Retourne (contenu_pdf, nom_fichier) si la tâche est terminée."""
        with self._lock:
            record = self._records.get(task_id)
            if record is None:
                raise TaskNotFoundError(task_id)
            if record.state.status != TaskStatus.done:
                raise ReportNotReadyError(
                    "Le rapport PDF n'est disponible que lorsque la tâche est terminée."
                )
            if record.report_id is None:
                record.report_id = f"r-{task_id[:8]}"
            task_snapshot = record.state.to_task(report_id=record.report_id)
            report_id = record.report_id

        self.settings.ensure_dirs()
        pdf_path = self.settings.reports_dir / f"{report_id}.pdf"
        if not pdf_path.is_file():
            pdf_bytes = self._report_builder(task_snapshot)
            pdf_path.write_bytes(pdf_bytes)
        else:
            pdf_bytes = pdf_path.read_bytes()
        return pdf_bytes, f"labmind_rapport_{task_id[:8]}.pdf"

    def delete_task(self, task_id: str) -> bool:
        """Supprime la tâche ainsi que les fichiers uploadés et rapports associés."""
        with self._lock:
            record = self._records.pop(task_id, None)
            if record is None:
                return False
            _cleanup_file(record.state.file_path)
            if record.report_id:
                _cleanup_file(self.settings.reports_dir / f"{record.report_id}.pdf")
            logger.info("Tâche supprimée : %s", task_id)
            return True