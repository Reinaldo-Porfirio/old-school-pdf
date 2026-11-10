"""Coordena o estágio, a publicação e o cancelamento das saídas."""

from collections.abc import Callable
from pathlib import Path

from docforge.application.job_service import JobRegistry
from docforge.domain.errors import DocForgeError
from docforge.domain.tasks import TaskSpec, TaskState
from docforge.infrastructure.local_files import OutputFile


class PdfOutputTask:
    def __init__(
        self,
        jobs: JobRegistry,
        description: str,
        outputs: list[OutputFile],
        sources: tuple[Path, ...],
        notify: Callable[[], None],
    ) -> None:
        self.jobs = jobs
        self.outputs = outputs
        self.sources = sources
        self.notify = notify
        self.task_id = jobs.submit(TaskSpec("pdf_export", description))
        notify()

    @property
    def cancelled(self) -> bool:
        return self.jobs.token(self.task_id).requested

    def start(self) -> None:
        if self.jobs.status(self.task_id).state == TaskState.PENDING:
            self.jobs.start(self.task_id)
            self.notify()

    def cancel(self) -> None:
        self.jobs.cancel(self.task_id)
        self.notify()

    def finish(self, error: str | None = None, *, detail: str = "") -> tuple[bool, str]:
        committed = False
        try:
            if error is None and not self.cancelled:
                for output in self.outputs:
                    output.check(self.sources)
                for output in self.outputs:
                    output.publish(self.sources)
                committed = True
        except (OSError, DocForgeError) as failure:
            for output in self.outputs:
                output.rollback_new()
            error = (
                str(failure)
                if isinstance(failure, DocForgeError)
                else "Não foi possível publicar o PDF. Verifique o acesso à pasta de destino."
            )
        finally:
            for output in self.outputs:
                output.cleanup()
        result = self.outputs[0].destination if committed else None
        self.start()
        if not self.jobs.status(self.task_id).state.terminal:
            self.jobs.finish(
                self.task_id, result=result, error=error, detail=detail if committed else ""
            )
        self.notify()
        if self.cancelled:
            return False, "Exportação cancelada."
        backups = [output.backup.name for output in self.outputs if output.backup]
        if committed:
            message = (
                f"{len(self.outputs)} PDF(s) gravado(s)."
                if len(self.outputs) > 1
                else f"PDF gravado em {result.name}."
            )
        else:
            message = error or "A exportação não foi concluída."
        if backups:
            message += " Cópia de segurança em " + ", ".join(backups) + "."
        return committed, message
