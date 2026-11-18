"""Routes HTTP /v1 conformes au contrat API v1."""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, File, Request, Response, UploadFile, status

from app.agent.orchestrator import InvalidAnswerError, InvalidQuestionStateError
from app.schemas import AnswerIn, Task

from .errors import ApiError
from .store import ReportNotReadyError, TaskManager, TaskNotFoundError

router = APIRouter(prefix="/v1", tags=["tasks"])


def _get_manager(request: Request) -> TaskManager:
    return request.app.state.task_manager


@router.get("/health")
def health() -> dict[str, str]:
    """Vérifie que le service API répond."""
    return {"status": "ok"}


@router.post(
    "/tasks",
    response_model=Task,
    status_code=status.HTTP_202_ACCEPTED,
)
def create_task(
    request: Request,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
) -> Task:
    """Dépose un document PDF ou image et démarre l'analyse en arrière-plan."""
    manager = _get_manager(request)
    settings = manager.settings

    filename = Path(file.filename or "").name
    suffix = Path(filename).suffix.lower()
    if suffix not in settings.allowed_extensions:
        raise ApiError(
            status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            "unsupported_format",
            "Format non supporté (pdf, png, jpg, jpeg).",
        )

    content = file.file.read(settings.max_upload_bytes + 1)
    if not content:
        raise ApiError(
            status.HTTP_400_BAD_REQUEST,
            "invalid_request",
            "Le fichier déposé est vide.",
        )

    if len(content) > settings.max_upload_bytes:
        raise ApiError(
            status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            "file_too_large",
            f"Le fichier dépasse la limite autorisée ({settings.max_upload_bytes} octets).",
        )

    task = manager.create_task(original_filename=filename, content=content)
    background_tasks.add_task(manager.process_task, task.task_id)
    return task


@router.get("/tasks/{task_id}", response_model=Task)
def get_task(task_id: str, request: Request) -> Task:
    """Retourne le statut et le résultat courant d'une tâche."""
    manager = _get_manager(request)
    task = manager.get_task(task_id)
    if task is None:
        raise ApiError(
            status.HTTP_404_NOT_FOUND,
            "task_not_found",
            "Tâche introuvable ou supprimée.",
        )
    return task


@router.post("/tasks/{task_id}/answer", response_model=Task)
def answer_task(task_id: str, body: AnswerIn, request: Request) -> Task:
    """Transmet la réponse utilisateur à une question de l'agent et reprend le traitement."""
    manager = _get_manager(request)
    try:
        return manager.answer_task(task_id, body)
    except TaskNotFoundError as exc:
        raise ApiError(
            status.HTTP_404_NOT_FOUND,
            "task_not_found",
            "Tâche introuvable ou supprimée.",
        ) from exc
    except InvalidQuestionStateError as exc:
        raise ApiError(
            status.HTTP_409_CONFLICT,
            "invalid_state",
            str(exc),
        ) from exc
    except InvalidAnswerError as exc:
        raise ApiError(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "invalid_answer",
            str(exc),
        ) from exc


@router.get("/tasks/{task_id}/report.pdf")
def download_report_pdf(task_id: str, request: Request) -> Response:
    """Télécharge le rapport PDF lorsque la tâche est terminée (`done`)."""
    manager = _get_manager(request)
    try:
        pdf_bytes, filename = manager.get_report_pdf(task_id)
    except TaskNotFoundError as exc:
        raise ApiError(
            status.HTTP_404_NOT_FOUND,
            "task_not_found",
            "Tâche introuvable ou supprimée.",
        ) from exc
    except ReportNotReadyError as exc:
        raise ApiError(
            status.HTTP_409_CONFLICT,
            "invalid_state",
            str(exc),
        ) from exc

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.delete("/tasks/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_task(task_id: str, request: Request) -> Response:
    """Supprime immédiatement la tâche, son fichier uploadé et son rapport."""
    manager = _get_manager(request)
    deleted = manager.delete_task(task_id)
    if not deleted:
        raise ApiError(
            status.HTTP_404_NOT_FOUND,
            "task_not_found",
            "Tâche introuvable ou déjà supprimée.",
        )
    return Response(status_code=status.HTTP_204_NO_CONTENT)