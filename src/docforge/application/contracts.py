"""Contratos de operações de documentos e de acompanhamento de tarefas."""

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol
from uuid import UUID

from docforge.domain.models import DocumentMetadata, DocumentSession
from docforge.domain.tasks import CancellationToken, TaskRecord, TaskSpec


class DocumentService(Protocol):
    def open(
        self, path: Path, password_callback: Callable[[], str | None] | None = None
    ) -> DocumentSession: ...

    def inspect(self, session: DocumentSession) -> DocumentMetadata: ...

    def close(self, session: DocumentSession) -> None: ...


@dataclass(frozen=True, slots=True)
class ImageBuffer:
    data: bytes
    width: int
    height: int
    stride: int
    format: str


class RenderService(Protocol):
    def render_page(
        self, session: DocumentSession, page_index: int, zoom: float, rotation: int
    ) -> ImageBuffer: ...


class JobService(Protocol):
    """Registro/coordenador; o contrato não implica que um executor exista."""

    def submit(self, task: TaskSpec) -> UUID: ...

    def cancel(self, task_id: UUID) -> None: ...

    def status(self, task_id: UUID) -> TaskRecord: ...

    def list_tasks(self) -> tuple[TaskRecord, ...]: ...

    def token(self, task_id: UUID) -> CancellationToken: ...
