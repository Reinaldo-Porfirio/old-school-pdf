"""Sessões PDF, prioridade de operações e cache de páginas."""

from collections import OrderedDict, deque
from collections.abc import Callable
from contextlib import suppress
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import TYPE_CHECKING
from uuid import UUID

from PySide6.QtCore import QObject, QTimer, Signal

from oldschoolpdf.application.contracts import ImageBuffer
from oldschoolpdf.application.job_service import JobRegistry
from oldschoolpdf.application.pdf_output import PdfOutputTask
from oldschoolpdf.domain.editing import AnnotationInfo, FormField
from oldschoolpdf.domain.models import DocumentSession, SignatureState
from oldschoolpdf.domain.tasks import TaskSpec, TaskState
from oldschoolpdf.domain.viewer import MAX_SEARCH_HITS, PdfInfo, PdfRect, RasterRequest, SearchHit

if TYPE_CHECKING:
    from oldschoolpdf.infrastructure.pdf_process import PdfProcess


@dataclass(frozen=True, slots=True)
class PageFrame:
    image: ImageBuffer
    width_pt: float
    height_pt: float
    scale: float
    rotation: int
    limited: bool

    @classmethod
    def from_reply(cls, result: dict, data: bytes) -> "PageFrame":
        width, height, stride = (result[key] for key in ("width", "height", "stride"))
        if not (0 < width <= 8192 and 0 < height <= 8192 and stride == 3 * width):
            raise ValueError("Dimensões inválidas.")
        if len(data) != stride * height:
            raise ValueError("Tamanho da imagem inválido.")
        image = ImageBuffer(data, width, height, stride, "RGB888")
        return cls(
            image,
            result["width_pt"],
            result["height_pt"],
            result["scale"],
            result["rotation"],
            result["limited"],
        )


class PdfWorkspace(QObject):
    jobs_changed = Signal()

    def __init__(
        self, jobs: JobRegistry, process_factory: Callable[[QObject], "PdfProcess"]
    ) -> None:
        super().__init__()
        self.jobs = jobs
        self.process_factory = process_factory
        self._queue: deque[PdfViewer] = deque()
        self._running: set[PdfViewer] = set()
        self._documents: set[PdfViewer] = set()
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._dispatch)
        self._cache: OrderedDict[tuple[UUID, RasterRequest], PageFrame] = OrderedDict()
        self._cache_bytes = 0
        self.configure(64, 2)

    def configure(self, cache_mib: int, parallelism: int) -> None:
        self._budget = cache_mib * 1024 * 1024
        self._parallelism = parallelism
        self._trim_cache()
        if self._queue:
            self._timer.start(0)

    def open(self, path: Path) -> "PdfViewer":
        viewer = PdfViewer(path, self)
        self._documents.add(viewer)
        self.wake(viewer)
        return viewer

    def wake(self, viewer: "PdfViewer") -> None:
        if viewer in self._documents and viewer not in self._running and viewer not in self._queue:
            self._queue.append(viewer)
            self._timer.start(0)

    def _dispatch(self) -> None:
        while self._queue and len(self._running) < self._parallelism:
            viewer = self._queue.popleft()
            self._running.add(viewer)
            if not viewer.dispatch():
                self._running.discard(viewer)

    def completed(self, viewer: "PdfViewer") -> None:
        self._running.discard(viewer)
        self.wake(viewer)
        if self._queue:
            self._timer.start(0)

    def discard(self, viewer: "PdfViewer") -> None:
        self._documents.discard(viewer)
        if viewer in self._queue:
            self._queue.remove(viewer)
        self.completed(viewer)
        self.invalidate(viewer.session.session_id)

    def invalidate(self, session: UUID) -> None:
        for key in [key for key in self._cache if key[0] == session]:
            self._cache_bytes -= len(self._cache.pop(key).image.data)

    def close(self) -> None:
        for viewer in tuple(self._documents):
            viewer.close()
        self._timer.stop()

    def cancel_job(self, task_id: UUID) -> None:
        for viewer in tuple(self._documents):
            if viewer.open_job == task_id:
                viewer.cancel_open()
                return
            if viewer.search_job == task_id:
                viewer.cancel_search()
                return
            if viewer.output and viewer.output.task_id == task_id:
                viewer.cancel_export()
                return

    def cached(self, session: UUID, spec: RasterRequest) -> PageFrame | None:
        key = (session, spec)
        frame = self._cache.get(key)
        if frame is not None:
            self._cache.move_to_end(key)
        return frame

    def remember(self, session: UUID, spec: RasterRequest, frame: PageFrame) -> None:
        key = (session, spec)
        old = self._cache.pop(key, None)
        self._cache_bytes += len(frame.image.data) - (len(old.image.data) if old else 0)
        self._cache[key] = frame
        self._trim_cache()

    def _trim_cache(self) -> None:
        while self._cache_bytes > self._budget:
            _, frame = self._cache.popitem(last=False)
            self._cache_bytes -= len(frame.image.data)


class PdfViewer(QObject):
    changed = Signal()
    frame_ready = Signal(object)
    thumbnail_ready = Signal(int, object)
    search_changed = Signal()
    hit_selected = Signal()
    text_ready = Signal(str)
    message = Signal(str)
    opening_cancelled = Signal()
    objects_changed = Signal()
    edited = Signal()
    export_completed = Signal(bool, str)
    signatures_ready = Signal(object)
    continuous_frame_ready = Signal(object, object)

    def __init__(self, path: Path, workspace: PdfWorkspace) -> None:
        super().__init__(workspace)
        self.workspace = workspace
        self.session = DocumentSession(path)
        self._open_path = path
        self.info: PdfInfo | None = None
        self.state = "opening"
        self.notice = "Abrindo PDF…"
        self.page = 0
        self.rotation = 0
        self.active = False
        self.hits: list[SearchHit] = []
        self.selected_hit = -1
        self.search_page = 0
        self.searching = False
        self.search_notice = ""
        self.revision = self.saved_revision = 0
        self.has_saved_copy = False
        self.can_undo = self.can_redo = False
        self.signature_confirmed = False
        self.signatures_checked = False
        self.busy = ""
        self.annotations: tuple[AnnotationInfo, ...] = ()
        self.fields: tuple[FormField, ...] = ()
        self.output: PdfOutputTask | None = None
        self._save_revision = False
        self._command: tuple[str, dict] | None = None
        self._objects_page: int | None = None
        self._scratch: TemporaryDirectory | None = None
        self._continuous: deque[RasterRequest] = deque()
        self.open_job = self._job("pdf_open", "Abrir PDF")
        self.search_job: UUID | None = None
        self._search_query = ""
        self._search_generation = 0
        self._open_pending = True
        self._password: str | None = None
        self._render: RasterRequest | None = None
        self._render_pending = False
        self._thumbs: deque[RasterRequest] = deque()
        self._copy: tuple[int, PdfRect | None] | None = None
        self._inflight: tuple[str, object] | None = None
        self._worker = self._new_worker()

    def _new_worker(self) -> "PdfProcess":
        worker = self.workspace.process_factory(self)
        worker.reply.connect(self._reply)
        worker.failed.connect(self._fatal)
        worker.progress.connect(self._export_progress)
        return worker

    @property
    def can_recover(self) -> bool:
        return self.state == "error" and self.session.working_copy is not None

    def recover(self) -> None:
        if not self.can_recover:
            return
        self._worker.deleteLater()
        self._worker = self._new_worker()
        self._open_path = self.session.working_copy
        self.revision = 0
        self.saved_revision = -1 if self.session.dirty else 0
        self.can_undo = self.can_redo = False
        self.state = "opening"
        self.notice = "Reabrindo a última revisão de trabalho…"
        self.open_job = self._job("pdf_open", "Recuperar revisão do PDF")
        self._open_pending = True
        self.changed.emit()
        self.workspace.wake(self)

    def _job(self, kind: str, description: str) -> UUID:
        task = self.workspace.jobs.submit(TaskSpec(kind, description))
        self.workspace.jobs_changed.emit()
        return task

    def _start_job(self, task: UUID) -> None:
        if self.workspace.jobs.status(task).state == TaskState.PENDING:
            self.workspace.jobs.start(task)
            self.workspace.jobs_changed.emit()

    def _finish_job(self, task: UUID | None, *, error: str | None = None, cancel=False) -> None:
        if task is None:
            return
        jobs = self.workspace.jobs
        if cancel:
            jobs.cancel(task)
        if jobs.status(task).state == TaskState.PENDING:
            jobs.start(task)
        if not jobs.status(task).state.terminal:
            jobs.finish(task, error=error)
        self.workspace.jobs_changed.emit()

    def set_active(self, active: bool) -> None:
        self.active = active
        if active:
            self.workspace.wake(self)
        else:
            self._render = None
            self._render_pending = False
            self._copy = None
            self._thumbs.clear()
            self._continuous.clear()

    def submit_password(self, password: str) -> None:
        if self.state == "password":
            self._password = password
            self.state = "opening"
            self.notice = "Verificando senha…"
            self.changed.emit()
            self.workspace.wake(self)

    def cancel_open(self) -> None:
        if self.state in ("opening", "password"):
            if self.session.working_copy is not None:
                self._finish_job(self.open_job, cancel=True)
                self._fatal("Recuperação cancelada. A revisão de trabalho continua disponível.")
            else:
                self.close()
                self.opening_cancelled.emit()

    def go_to(self, page: int) -> None:
        if self.info and not self.busy and 0 <= page < self.info.page_count and page != self.page:
            self.page = page
            self._render = None
            self._render_pending = False
            self.annotations = ()
            self.fields = ()
            self.objects_changed.emit()
            self.changed.emit()

    def turn(self) -> None:
        if self.info:
            self.rotation = (self.rotation + 90) % 360
            self._render = None
            self._render_pending = False
            self._thumbs.clear()
            self.changed.emit()

    def release_render(self) -> None:
        self._render = None
        self._render_pending = False

    def render(self, spec: RasterRequest) -> None:
        if self.state == "ready" and self.active:
            if spec == self._render:
                return
            self._render = spec
            self._render_pending = True
            self.workspace.wake(self)

    def thumbnails(self, pages: list[int], dpr: float) -> None:
        self._thumbs = deque(
            RasterRequest(page, self.rotation, "thumbnail", 110, 106, dpr) for page in pages
        )
        if pages:
            self.workspace.wake(self)

    def continuous_pages(self, specs: list[RasterRequest]) -> None:
        self._continuous = deque(specs)
        if specs:
            self.workspace.wake(self)

    def request_objects(self) -> None:
        if self.info:
            self._objects_page = self.page
            self.workspace.wake(self)

    def _queue_command(self, operation: str, arguments: dict, label: str) -> bool:
        if self.state != "ready" or self.busy:
            return False
        self._command = (operation, arguments)
        self.busy = label
        self.changed.emit()
        self.workspace.wake(self)
        return True

    def change(self, action: str, values: dict, *, page: int | None = None) -> bool:
        if self.state != "ready" or self.busy:
            return False
        if self._scratch is None:
            try:
                self._scratch = TemporaryDirectory(
                    prefix="oldschoolpdf-edits-", ignore_cleanup_errors=True
                )
            except OSError:
                self.message.emit("Não foi possível criar a pasta temporária de trabalho.")
                return False
        return self._queue_command(
            "edit",
            {
                "action": action,
                "page": self.page if page is None else page,
                "values": values,
                "scratch": self._scratch.name,
                "confirmed": self.signature_confirmed,
            },
            "Aplicando alteração…",
        )

    def step(self, direction: int) -> None:
        self._queue_command("step", {"direction": direction}, "Restaurando revisão…")

    def export(
        self,
        task: PdfOutputTask,
        groups: list[list[tuple[int, int]] | None],
        *,
        save: bool,
        security: dict | None = None,
    ) -> bool:
        if self.state != "ready" or self.busy:
            task.finish("A aba está ocupada.")
            return False
        self.output = task
        self._save_revision = save
        arguments = {
            "outputs": [
                {"stage": str(output.stage), "ranges": ranges}
                for output, ranges in zip(task.outputs, groups, strict=True)
            ],
            "confirmed": self.signature_confirmed,
            "security": security,
        }
        return self._queue_command("export", arguments, "Gravando e validando PDF…")

    def verify_signatures(self, trust_paths: list[str]) -> None:
        self._queue_command(
            "verify_signatures", {"trust_paths": trust_paths}, "Verificando assinaturas locais…"
        )

    def _export_progress(self, update: dict) -> None:
        task = self.output
        if task and task.jobs.status(task.task_id).state == TaskState.RUNNING:
            task.jobs.update_progress(task.task_id, update["value"], detail=update["detail"])
            task.notify()

    def cancel_export(self) -> None:
        if self.output:
            self.output.cancel()
            if self._command and self._command[0] == "export":
                self._command = None
                self._finish_export()

    def _finish_export(self, error: str | None = None, *, detail: str = "") -> None:
        if self.output is None:
            return
        task, self.output = self.output, None
        saved, message = task.finish(error, detail=detail)
        if saved and self._save_revision:
            self.has_saved_copy = True
            self.saved_revision = self.revision
            self.session.dirty = False
        self.busy = ""
        self.changed.emit()
        self.export_completed.emit(saved, message)

    def _changed_revision(self, result: dict) -> None:
        if result["working_copy"] is not None:
            path = Path(result["working_copy"])
            if self._scratch is None or path.parent != Path(self._scratch.name):
                raise ValueError("Revisão fora da pasta de trabalho.")
            self.session.working_copy = path
        else:
            self.session.working_copy = (
                self._open_path if self._open_path != self.session.source_path else None
            )
        self.revision = result["revision"]
        self.signatures_checked = False
        self.session.dirty = self.revision != self.saved_revision
        self.info = replace(self.info, page_count=result["page_count"])
        self.page = result["page"]
        self.can_undo, self.can_redo = result["undo"], result["redo"]
        self.workspace.invalidate(self.session.session_id)
        self._render = self._objects_page = None
        self._render_pending = False
        self._thumbs.clear()
        self._continuous.clear()
        self.annotations = ()
        self.fields = ()
        self.cancel_search()
        self.hits.clear()
        self.selected_hit = -1
        self.search_notice = ""
        self.busy = ""
        self.edited.emit()
        self.objects_changed.emit()
        self.search_changed.emit()
        self.changed.emit()

    def copy(self, region: PdfRect | None) -> None:
        if self.info and self.info.copy_allowed:
            self._copy = (self.page, region)
            self.workspace.wake(self)

    def start_search(self, query: str) -> None:
        if self.state != "ready" or not query.strip():
            return
        self.cancel_search()
        self._search_generation += 1
        self._search_query = query
        self.hits.clear()
        self.selected_hit = -1
        self.search_page = 0
        self.searching = True
        self.search_notice = "Buscando…"
        self.search_job = self._job("pdf_search", "Buscar texto no PDF")
        self.search_changed.emit()
        self.workspace.wake(self)

    def cancel_search(self) -> None:
        if self.searching:
            self._finish_job(self.search_job, cancel=True)
            self.search_job = None
            self.searching = False
            self.search_notice = "Busca cancelada"
            self.search_changed.emit()

    def move_hit(self, delta: int) -> None:
        if self.hits:
            self._choose_hit((self.selected_hit + delta) % len(self.hits))

    def _choose_hit(self, index: int) -> None:
        self.selected_hit = index
        self.go_to(self.hits[index].page)
        self.hit_selected.emit()
        self.search_changed.emit()

    def _send(self, operation: str, arguments: dict, token=None) -> bool:
        self._inflight = (operation, token)
        self._worker.request(operation, arguments)
        return True

    def _send_raster(self, spec: RasterRequest) -> bool:
        cached = self.workspace.cached(self.session.session_id, spec)
        if cached is None:
            return self._send("render", asdict(spec), spec)
        self._show_frame(spec, cached)
        self.workspace.completed(self)
        return True

    def dispatch(self) -> bool:
        if self._open_pending:
            self._open_pending = False
            self._start_job(self.open_job)
            return self._send("open", {"path": str(self._open_path)})
        if self._password is not None:
            password, self._password = self._password, None
            return self._send("password", {"password": password})
        if self._command is not None:
            (operation, arguments), self._command = self._command, None
            if operation == "export":
                self.output.start()
            return self._send(operation, arguments)
        if self.state != "ready" or not self.active:
            return False
        if self._render_pending:
            self._render_pending = False
            return self._send_raster(self._render)
        if self._copy is not None:
            (page, region), self._copy = self._copy, None
            return self._send("copy", {"page": page, "region": region}, page)
        if self._objects_page is not None:
            page, self._objects_page = self._objects_page, None
            return self._send("objects", {"page": page}, page)
        if self._continuous:
            return self._send_raster(self._continuous.popleft())
        if self._thumbs:
            return self._send_raster(self._thumbs.popleft())
        if self.searching:
            self._start_job(self.search_job)
            return self._send(
                "search",
                {
                    "page": self.search_page,
                    "query": self._search_query,
                    "limit": MAX_SEARCH_HITS - len(self.hits),
                },
                self._search_generation,
            )
        return False

    def _show_frame(self, spec: RasterRequest, frame: PageFrame) -> None:
        if self.active and spec.rotation == self.rotation:
            if spec.zoom == "thumbnail":
                self.thumbnail_ready.emit(spec.page, frame)
            elif spec.zoom == "continuous":
                self.continuous_frame_ready.emit(spec, frame)
            elif spec == self._render:
                self.frame_ready.emit(frame)

    def _reply(self, reply: dict, data: bytes) -> None:
        if self._inflight is None or self.state == "closed":
            return
        (operation, token), self._inflight = self._inflight, None
        try:
            if "error" in reply:
                self._operation_error(operation, token, reply["error"])
            elif operation in ("open", "password"):
                self._opened(reply["result"])
            elif operation == "render":
                frame = PageFrame.from_reply(reply["result"], data)
                self.workspace.remember(self.session.session_id, token, frame)
                self._show_frame(token, frame)
            elif operation == "search":
                self._searched(token, reply["result"])
            elif operation in {"edit", "step"}:
                self._changed_revision(reply["result"])
            elif operation == "export":
                self._finish_export(detail=reply["result"].get("detail", ""))
            elif operation == "verify_signatures":
                self.signatures_checked = True
                self.busy = ""
                self.changed.emit()
                self.signatures_ready.emit(reply["result"]["signatures"])
            elif operation == "objects" and token == self.page:
                result = reply["result"]
                self.annotations = tuple(AnnotationInfo(**entry) for entry in result["annotations"])
                self.fields = tuple(FormField(**entry) for entry in result["fields"])
                self.objects_changed.emit()
            elif operation == "copy" and self.active and token == self.page:
                text = reply["result"]["text"]
                if text.strip():
                    self.text_ready.emit(text)
                else:
                    self.message.emit("A área não contém texto selecionável.")
        except (KeyError, TypeError, ValueError):
            self._fatal("O leitor de PDF devolveu dados inválidos.")
        finally:
            self.workspace.completed(self)

    def _opened(self, result: dict) -> None:
        self.signatures_checked = False
        if result["state"] == "password":
            self.state = "password"
            self.notice = (
                "Senha incorreta. Tente novamente."
                if result["incorrect"]
                else "Este PDF é protegido por senha."
            )
        else:
            self.info = PdfInfo(**{key: value for key, value in result.items() if key != "state"})
            self.session.signature_state = (
                SignatureState.SIGNED if self.info.signed else SignatureState.UNKNOWN
            )
            self.state = "ready"
            self.page = min(self.page, self.info.page_count - 1)
            self.notice = "O leitor reparou a estrutura em memória." if self.info.repaired else ""
            if self._open_path != self.session.source_path:
                for path in self._open_path.parent.glob("revision-*.pdf"):
                    if path != self._open_path:
                        with suppress(OSError):
                            path.unlink()
                self.edited.emit()
                self.message.emit("Revisão recuperada. O histórico recomeça a partir desta versão.")
            self._finish_job(self.open_job)
        self.changed.emit()

    def _searched(self, generation: int, result: dict) -> None:
        if generation != self._search_generation or not self.searching:
            return
        self.hits.extend(
            SearchHit(self.search_page, tuple(tuple(region) for region in hit))
            for hit in result["hits"]
        )
        if self.selected_hit < 0 and self.hits:
            self._choose_hit(0)
        self.search_page += 1
        count = self.info.page_count
        progress = min(99, self.search_page * 100 // count)
        if len(self.hits) == MAX_SEARCH_HITS:
            self.search_notice = (
                "Limite de 1.000 ocorrências"
                if result["has_more"] or self.search_page < count
                else "Busca concluída"
            )
            self._end_search()
        elif self.search_page >= count:
            self.search_notice = "Busca concluída" if self.hits else "Nenhuma ocorrência"
            self._end_search()
        else:
            self.search_notice = f"Buscando {self.search_page}/{count}"
            if progress != self.workspace.jobs.status(self.search_job).progress:
                self.workspace.jobs.update_progress(self.search_job, progress)
                self.workspace.jobs_changed.emit()
        self.search_changed.emit()

    def _end_search(self, error: str | None = None) -> None:
        self.searching = False
        self._finish_job(self.search_job, error=error)
        self.search_job = None

    def _operation_error(self, operation: str, token, error: str) -> None:
        if operation in ("open", "password"):
            self._fatal(error)
        elif operation == "export":
            self._finish_export(error)
        elif operation in {"edit", "step", "verify_signatures"}:
            self.busy = ""
            self.changed.emit()
            self.message.emit(error)
        elif operation == "objects" and token == self.page:
            self.message.emit(error)
        elif operation == "search":
            if self.searching and token == self._search_generation:
                self.search_notice = error
                self._end_search(error)
                self.search_changed.emit()
        elif self.active and (
            (operation == "render" and token == self._render)
            or (operation == "copy" and token == self.page)
        ):
            self.message.emit(error)

    def _fatal(self, error: str) -> None:
        self.state = "error"
        self.notice = error
        self.info = None
        self._worker.stop()
        self._open_pending = False
        self._inflight = self._password = self._copy = self._objects_page = None
        self.release_render()
        self._thumbs.clear()
        self._continuous.clear()
        self.annotations = self.fields = ()
        self.workspace.invalidate(self.session.session_id)
        if self.output:
            self._finish_export(error)
        self.busy = ""
        self._command = None
        self._finish_job(self.open_job, error=error)
        if self.searching:
            self._end_search(error)
        self.hits.clear()
        self.selected_hit = -1
        self.search_notice = ""
        self.workspace.completed(self)
        self.changed.emit()

    def close(self) -> None:
        if self.state == "closed":
            return
        self.state = "closed"
        self._password = None
        self._inflight = None
        self.cancel_search()
        self._worker.stop()
        if self.output:
            self.output.cancel()
            self.output.finish()
            self.output = None
        if self._scratch:
            self._scratch.cleanup()
            self._scratch = None
        self._finish_job(self.open_job, cancel=True)
        self.workspace.discard(self)
        self.deleteLater()
