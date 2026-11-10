"""Fila sequencial de entradas independentes com progresso e retomada local."""

from collections import deque
from dataclasses import asdict, replace
from pathlib import Path
from uuid import UUID

from PySide6.QtCore import QObject, QTimer, Signal

from docforge.application.job_service import JobRegistry
from docforge.domain.errors import DocForgeError
from docforge.domain.media import MEDIA_LABELS, MediaOperation, MediaRequest
from docforge.domain.tasks import TaskRecord, TaskSpec, TaskState
from docforge.infrastructure.media_output import MediaOutput

FOLDER_LABELS = {
    MediaOperation.OCR: "OCR",
    MediaOperation.RENDER: "Páginas",
    MediaOperation.IMAGES_PDF: "Imagens em PDF",
    MediaOperation.TEXT: "Texto",
    MediaOperation.EXTRACT_IMAGES: "Imagens",
    MediaOperation.OPTIMIZE: "Otimizado",
    MediaOperation.SPLIT: "Partes",
    MediaOperation.MERGE: "PDFs mesclados",
}


class MediaRunner(QObject):
    changed = Signal()
    completed = Signal()

    def __init__(self, jobs: JobRegistry, process_factory, parent: QObject) -> None:
        super().__init__(parent)
        self.jobs = jobs
        self.process_factory = process_factory
        self.request: MediaRequest | None = None
        self.active = False
        self._ids: tuple[UUID, ...] = ()
        self._pending: deque[UUID] = deque()
        self._current: UUID | None = None
        self._process = None
        self._output: MediaOutput | None = None
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._next)

    def start(self, request: MediaRequest) -> None:
        if self.active:
            raise DocForgeError("Já há um lote na fila.")
        label = MEDIA_LABELS[request.operation]
        self.request = request
        self.active = True
        self._ids = tuple(
            self.jobs.submit(
                TaskSpec(
                    "media_" + request.operation,
                    f"{label} · {group[0].name}" if len(group) == 1 else label,
                    group,
                    request.destination,
                )
            )
            for group in request.groups()
        )
        self._pending = deque(self._ids)
        self.changed.emit()
        self._timer.start(0)

    def records(self) -> tuple[TaskRecord, ...]:
        return tuple(self.jobs.status(task_id) for task_id in self._ids)

    def can_retry(self) -> bool:
        return not self.active and any(
            item.state in {TaskState.FAILED, TaskState.CANCELLED} for item in self.records()
        )

    def retry(self) -> None:
        if self.can_retry():
            inputs = tuple(
                path
                for record in self.records()
                if record.state in {TaskState.FAILED, TaskState.CANCELLED}
                for path in record.spec.inputs
            )
            self.start(replace(self.request, inputs=inputs))

    def _next(self) -> None:
        while self._pending:
            task_id = self._pending.popleft()
            if self.jobs.status(task_id).state == TaskState.PENDING:
                self._start_entry(task_id)
                return
        self.active = False
        self.changed.emit()
        self.completed.emit()

    def _start_entry(self, task_id: UUID) -> None:
        self._current = task_id
        self.jobs.start(task_id)
        self.changed.emit()
        if self._current != task_id:
            return
        try:
            request = self.request
            group = self.jobs.status(task_id).spec.inputs
            label = FOLDER_LABELS[request.operation]
            if len(group) == 1:
                label = f"{group[0].stem[:74]} - {label}"
            self._output = MediaOutput.prepare(request.destination, label)
        except (OSError, DocForgeError) as error:
            self._finish(
                error=str(error)
                if isinstance(error, DocForgeError)
                else "Não foi possível criar a pasta temporária no destino."
            )
            return
        process = self._process = self.process_factory(self)
        process.progress.connect(self._progress)
        process.reply.connect(self._reply)
        process.failed.connect(lambda error: self._finish(error=error))
        process.request(
            "process_media",
            {
                "operation": request.operation,
                "inputs": [str(path) for path in group],
                "stage": str(self._output.stage),
                "options": asdict(request.options),
            },
        )

    def _progress(self, event: dict) -> None:
        if self._current is None or self.jobs.status(self._current).state != TaskState.RUNNING:
            return
        value, detail = event.get("value"), event.get("detail")
        if isinstance(value, int) and isinstance(detail, str) and 0 <= value < 100:
            self.jobs.update_progress(self._current, value, detail=detail[:300])
            self.changed.emit()

    def _reply(self, reply: dict, _payload: bytes) -> None:
        if "error" in reply:
            self._finish(error=reply["error"])
        else:
            result = reply.get("result", {})
            count = result.get("files")
            if not isinstance(count, int) or count < 0:
                self._finish(error="O processo retornou um resultado inválido.")
            else:
                self._finish(count=count, detail=result.get("detail", ""))

    def _finish(self, *, count: int = 0, error: str | None = None, detail: str = "") -> None:
        task_id, self._current = self._current, None
        process, self._process = self._process, None
        stage, self._output = self._output, None
        if task_id is None:
            return
        if process is not None:
            process.stop()
            process.deleteLater()
        result: Path | None = None
        try:
            if stage and count and not error and not self.jobs.token(task_id).requested:
                result = stage.publish(count)
        except (OSError, DocForgeError) as failure:
            error = (
                str(failure)
                if isinstance(failure, DocForgeError)
                else "Não foi possível publicar o resultado na pasta de destino."
            )
        finally:
            if stage:
                stage.cleanup()
        self.jobs.finish(task_id, result=result, error=error, detail=detail)
        self.changed.emit()
        self._timer.start(0)

    def cancel(self, task_id: UUID) -> None:
        if not self.active or task_id not in self._ids:
            return
        self.jobs.cancel(task_id)
        if task_id == self._current:
            self._finish()
        else:
            self.changed.emit()

    def cancel_all(self) -> None:
        if self.active:
            for task_id in self._ids:
                self.jobs.cancel(task_id)
            self._finish()
            self.changed.emit()
