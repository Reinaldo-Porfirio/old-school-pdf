"""Transporte assíncrono e limitado para o processo leitor."""

import json
import sys

from PySide6.QtCore import QObject, QProcess, QTimer, Signal

from oldschoolpdf.domain.viewer import MAX_RASTER_BYTES, MAX_REPLY_HEADER
from oldschoolpdf.infrastructure.pdf_worker import FRAME, WORKER_FLAG


def worker_command() -> tuple[str, list[str]]:
    """Programa e argumentos do processo leitor, no código-fonte ou no executável."""
    if getattr(sys, "frozen", False):
        # No .exe não há interpretador separado: o próprio executável vira o leitor.
        return sys.executable, [WORKER_FLAG]
    return sys.executable, ["-I", "-u", "-m", "oldschoolpdf.infrastructure.pdf_worker"]


class PdfProcess(QObject):
    reply = Signal(object, object)
    failed = Signal(str)
    progress = Signal(object)
    TIMEOUT_MS = 20_000
    EDIT_TIMEOUT_MS = 120_000

    def __init__(self, parent: QObject) -> None:
        super().__init__(parent)
        self.process = QProcess(self)
        program, arguments = worker_command()
        self.process.setProgram(program)
        self.process.setArguments(arguments)
        self.process.started.connect(self._write)
        self.process.readyReadStandardOutput.connect(self._read)
        self.process.readyReadStandardError.connect(self.process.readAllStandardError)
        self.process.errorOccurred.connect(self._process_error)
        self.process.finished.connect(self._exited)
        self.deadline = QTimer(self)
        self.deadline.setSingleShot(True)
        self.deadline.timeout.connect(self._timed_out)
        self._pending: bytes | None = None
        self._buffer = bytearray()
        self._stopped = False
        self._allow_progress = False

    def request(self, operation: str, arguments: dict) -> None:
        self._pending = json.dumps({"op": operation, "args": arguments}).encode() + b"\n"
        self._allow_progress = operation in {"process_media", "export"}
        duration = (
            self.EDIT_TIMEOUT_MS
            if operation
            in {
                "edit",
                "step",
                "export",
                "merge",
                "inspect_inputs",
                "process_media",
                "verify_signatures",
            }
            else self.TIMEOUT_MS
        )
        self.deadline.start(duration)
        if self.process.state() == QProcess.ProcessState.NotRunning:
            self.process.start()
        else:
            self._write()

    def _write(self) -> None:
        pending, self._pending = self._pending, None
        if pending is not None and self.process.write(pending) < 0:
            self._abort("Não foi possível comunicar com o leitor de PDF.")

    def _read(self) -> None:
        chunk = self.process.readAllStandardOutput()
        if self._stopped:
            return
        self._buffer.extend(bytes(chunk))
        while not self._stopped and self._read_frame():
            pass

    def _read_frame(self) -> bool:
        if len(self._buffer) < FRAME.size:
            return False
        header_size, body_size = FRAME.unpack_from(self._buffer)
        if not 0 < header_size <= MAX_REPLY_HEADER or body_size > MAX_RASTER_BYTES:
            self._abort("O leitor de PDF devolveu uma resposta inválida.")
            return False
        body_start = FRAME.size + header_size
        end = body_start + body_size
        if len(self._buffer) < end:
            return False
        if not self.deadline.isActive():
            self._abort("O leitor de PDF devolveu uma resposta inesperada.")
            return False
        try:
            reply = json.loads(self._buffer[FRAME.size : body_start])
        except (UnicodeError, ValueError, RecursionError):
            self._abort("O leitor de PDF devolveu uma resposta inválida.")
            return False
        if not isinstance(reply, dict):
            self._abort("O leitor de PDF devolveu uma resposta inválida.")
            return False
        body = bytes(memoryview(self._buffer)[body_start:end])
        del self._buffer[:end]
        if "progress" in reply and self._allow_progress and not body:
            self.deadline.start(self.EDIT_TIMEOUT_MS)
            self.progress.emit(reply["progress"])
            return True
        if "progress" in reply or self._buffer:
            self._abort("O leitor de PDF devolveu uma resposta inesperada.")
            return False
        self.deadline.stop()
        self.reply.emit(reply, body)
        return False

    def _timed_out(self) -> None:
        self._abort("O leitor excedeu o prazo desta operação. Reabra o PDF para tentar novamente.")

    def _process_error(self, error: QProcess.ProcessError) -> None:
        if error == QProcess.ProcessError.FailedToStart:
            self._abort("Não foi possível iniciar o leitor de PDF. Verifique a instalação.")
        elif error in (QProcess.ProcessError.ReadError, QProcess.ProcessError.WriteError):
            self._abort("A comunicação com o leitor de PDF foi interrompida.")

    def _exited(self) -> None:
        self._abort(
            "O leitor de PDF encerrou inesperadamente. Reabra o arquivo para tentar novamente."
        )

    def _abort(self, message: str) -> None:
        if not self._stopped:
            self.stop()
            self.failed.emit(message)

    def stop(self) -> None:
        self._stopped = True
        self.deadline.stop()
        self._pending = None
        self._buffer.clear()
        if self.process.state() != QProcess.ProcessState.NotRunning:
            self.process.kill()
            self.process.waitForFinished(250)
