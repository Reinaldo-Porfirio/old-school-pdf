"""Registro em memória das tarefas e suas transições."""

from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from threading import RLock
from uuid import UUID, uuid4

from docforge.domain.errors import InvalidTransitionError
from docforge.domain.tasks import CancellationToken, TaskRecord, TaskSpec, TaskState


class JobRegistry:
    """Snapshot imutável e lock protegem transições vindas de futuros workers."""

    def __init__(self) -> None:
        self._records: dict[UUID, TaskRecord] = {}
        self._tokens: dict[UUID, CancellationToken] = {}
        self._lock = RLock()

    def submit(self, task: TaskSpec) -> UUID:
        with self._lock:
            task_id = uuid4()
            self._records[task_id] = TaskRecord(task_id, task, TaskState.PENDING, datetime.now(UTC))
            self._tokens[task_id] = CancellationToken()
            return task_id

    def status(self, task_id: UUID) -> TaskRecord:
        with self._lock:
            return self._records[task_id]

    def list_tasks(self) -> tuple[TaskRecord, ...]:
        with self._lock:
            return tuple(self._records.values())

    def token(self, task_id: UUID) -> CancellationToken:
        with self._lock:
            return self._tokens[task_id]

    def start(self, task_id: UUID) -> None:
        with self._lock:
            record = self.status(task_id)
            if record.state != TaskState.PENDING:
                raise InvalidTransitionError("Somente tarefas na fila podem iniciar.")
            self._records[task_id] = replace(
                record, state=TaskState.RUNNING, started_at=datetime.now(UTC)
            )

    def update_progress(self, task_id: UUID, progress: int, *, detail: str = "") -> None:
        with self._lock:
            record = self.status(task_id)
            if record.state != TaskState.RUNNING or not record.progress <= progress <= 99:
                raise InvalidTransitionError("Progresso inválido para a tarefa atual.")
            self._records[task_id] = replace(record, progress=progress, detail=detail)

    def cancel(self, task_id: UUID) -> None:
        with self._lock:
            record = self.status(task_id)
            if record.state.terminal:
                return
            self.token(task_id).request()
            state = (
                TaskState.CANCELLED if record.state == TaskState.PENDING else TaskState.CANCELLING
            )
            self._records[task_id] = replace(
                record,
                state=state,
                finished_at=datetime.now(UTC) if state == TaskState.CANCELLED else None,
            )

    def finish(
        self,
        task_id: UUID,
        *,
        result: Path | None = None,
        error: str | None = None,
        detail: str = "",
    ) -> None:
        """Worker só chama depois de validar saída ou limpar temporários cancelados."""
        with self._lock:
            record = self.status(task_id)
            if record.state not in (TaskState.RUNNING, TaskState.CANCELLING):
                raise InvalidTransitionError("A tarefa não está em execução.")
            cancelled = self.token(task_id).requested
            state = (
                TaskState.CANCELLED
                if cancelled
                else TaskState.FAILED
                if error is not None
                else TaskState.SUCCEEDED
            )
            self._records[task_id] = replace(
                record,
                state=state,
                finished_at=datetime.now(UTC),
                progress=100 if state == TaskState.SUCCEEDED else record.progress,
                result=result if state == TaskState.SUCCEEDED else None,
                error=error if state == TaskState.FAILED else None,
                detail=detail,
            )
