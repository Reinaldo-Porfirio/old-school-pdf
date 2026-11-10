"""Validação de caminhos e publicação de PDFs em uma unidade local."""

import ctypes
import os
import stat
import tempfile
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from oldschoolpdf.domain.errors import OldSchoolPDFError

MAX_PDF_BYTES = 512 * 1024 * 1024
FileStamp = tuple[int, int, int, int]


def file_stamp(path: Path | int) -> FileStamp:
    info = os.fstat(path) if isinstance(path, int) else path.stat()
    return info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns


def check_local(path: Path, *, missing_leaf: bool = False) -> None:
    if not path.is_absolute():
        raise OldSchoolPDFError("Escolha um caminho absoluto em uma unidade local.")
    if os.name == "nt":
        if len(path.drive) != 2 or ctypes.windll.kernel32.GetDriveTypeW(path.anchor) == 4:
            raise OldSchoolPDFError("Escolha um caminho em uma unidade local.")
    elif str(path).startswith("//"):
        raise OldSchoolPDFError("Escolha um caminho em uma unidade local.")
    for component in reversed((path, *path.parents)):
        try:
            info = component.lstat()
        except FileNotFoundError:
            if missing_leaf and component == path:
                return
            raise
        attributes = getattr(info, "st_file_attributes", 0)
        if stat.S_ISLNK(info.st_mode) or attributes & (0x400 | 0x1000 | 0x40000 | 0x400000):
            raise OldSchoolPDFError("Use um caminho local fora de atalhos ou pastas sob demanda.")


def check_pdf(path: Path) -> None:
    if path.suffix.casefold() != ".pdf":
        raise OldSchoolPDFError("Escolha um arquivo local com extensão .pdf.")
    check_local(path)
    if not stat.S_ISREG(path.stat().st_mode):
        raise OldSchoolPDFError("O caminho selecionado não é um arquivo PDF regular.")
    with path.open("rb") as source:
        if os.fstat(source.fileno()).st_size > MAX_PDF_BYTES:
            raise OldSchoolPDFError("Este PDF excede o limite de leitura de 512 MiB.")
        if b"%PDF-" not in source.read(1024):
            raise OldSchoolPDFError("O arquivo não tem um cabeçalho PDF válido.")


def same_target(path: Path, source: Path) -> bool:
    if os.path.normcase(os.path.abspath(path)) == os.path.normcase(os.path.abspath(source)):
        return True
    try:
        check_local(source)
        return path.samefile(source)
    except (OSError, OldSchoolPDFError):
        return False


def _install_new(stage: Path, destination: Path) -> None:
    if os.name == "nt":
        os.rename(stage, destination)
    else:
        os.link(stage, destination)


@dataclass(slots=True)
class OutputFile:
    destination: Path
    stage: Path
    expected: FileStamp | None
    backup: Path | None = None
    installed: FileStamp | None = None

    @classmethod
    def prepare(
        cls, destination: Path, sources: tuple[Path, ...], *, expected: FileStamp | None = None
    ) -> "OutputFile":
        if destination.suffix.casefold() != ".pdf":
            raise OldSchoolPDFError("A saída precisa ter extensão .pdf.")
        try:
            check_local(destination, missing_leaf=True)
            if any(same_target(destination, source) for source in sources):
                raise OldSchoolPDFError("Escolha outro destino para preservar o PDF de origem.")
            exists = destination.exists()
            if exists:
                check_pdf(destination)
                if expected is None or file_stamp(destination) != expected:
                    raise OldSchoolPDFError("O destino já existe ou mudou. Escolha outro nome.")
            elif expected is not None:
                raise OldSchoolPDFError("O destino mudou. Escolha novamente onde gravar.")
            descriptor, name = tempfile.mkstemp(
                prefix=".oldschoolpdf-", suffix=".part.pdf", dir=destination.parent
            )
            os.close(descriptor)
        except OSError:
            raise OldSchoolPDFError(
                "Não foi possível criar o temporário na pasta de destino."
            ) from None
        return cls(destination, Path(name), expected)

    def check(self, sources: tuple[Path, ...]) -> None:
        check_local(self.destination, missing_leaf=True)
        if any(same_target(self.destination, source) for source in sources):
            raise OldSchoolPDFError("O destino passou a apontar para um dos originais.")
        current = file_stamp(self.destination) if self.destination.exists() else None
        if current != self.expected:
            raise OldSchoolPDFError("O destino mudou durante a gravação. Escolha outro nome.")
        check_pdf(self.stage)

    def publish(self, sources: tuple[Path, ...]) -> None:
        self.check(sources)
        stamp = file_stamp(self.stage)
        if self.expected is None:
            _install_new(self.stage, self.destination)
        else:
            name = f"{self.destination.stem}.backup-{uuid4().hex[:10]}.pdf"
            backup = self.destination.with_name(name)
            # O vínculo preserva a versão que está no destino, sem copiar arquivos grandes na UI.
            os.link(self.destination, backup)
            self.backup = backup
            if file_stamp(backup) != self.expected or file_stamp(self.destination) != self.expected:
                raise OldSchoolPDFError("O destino mudou antes da substituição.")
            os.replace(self.stage, self.destination)
        self.installed = stamp

    def cleanup(self) -> None:
        with suppress(OSError):
            self.stage.unlink(missing_ok=True)

    def rollback_new(self) -> None:
        if self.expected is None and self.installed is not None:
            try:
                if file_stamp(self.destination) == self.installed:
                    self.destination.unlink()
            except OSError:
                pass
