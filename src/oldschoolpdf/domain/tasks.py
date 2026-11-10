"""Contratos de tarefas independentes do executor e da UI."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from threading import Event
from uuid import UUID


class TaskState(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    CANCELLING = "cancelling"
    CANCELLED = "cancelled"
    SUCCEEDED = "succeeded"
    FAILED = "failed"

    @property
    def terminal(self) -> bool:
        return self in (self.CANCELLED, self.SUCCEEDED, self.FAILED)


@dataclass(frozen=True, slots=True)
class TaskSpec:
    kind: str
    description: str
    inputs: tuple[Path, ...] = ()
    output: Path | None = None

    def __post_init__(self) -> None:
        if not self.kind.strip() or not self.description.strip():
            raise ValueError("Tipo e descrição da tarefa são obrigatórios.")


@dataclass(frozen=True, slots=True)
class TaskRecord:
    task_id: UUID
    spec: TaskSpec
    state: TaskState
    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None
    progress: int = 0
    result: Path | None = None
    error: str | None = None
    detail: str = ""


@dataclass(slots=True)
class CancellationToken:
    """O worker futuro consulta o token e confirma a limpeza antes de concluir."""

    _event: Event = field(default_factory=Event, repr=False)

    @property
    def requested(self) -> bool:
        return self._event.is_set()

    def request(self) -> None:
        self._event.set()
