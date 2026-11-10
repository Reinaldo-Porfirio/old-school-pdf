"""Publica todos os resultados de uma entrada em um diretório novo."""

import os
import tempfile
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path
from shutil import rmtree
from time import sleep

from docforge.domain.errors import DocForgeError
from docforge.infrastructure.local_files import check_local, file_stamp

MAX_MEDIA_FILES = 2000
OUTPUT_EXTENSIONS = {".pdf", ".txt", ".png", ".jpg"}


@dataclass(frozen=True, slots=True)
class MediaOutput:
    stage: Path
    label: str
    identity: tuple[int, int]

    @classmethod
    def prepare(cls, destination: Path, label: str) -> "MediaOutput":
        check_local(destination)
        if not destination.is_dir():
            raise DocForgeError("Escolha uma pasta local para os resultados.")
        stage = Path(tempfile.mkdtemp(prefix=".docforge-lote-", dir=destination))
        return cls(stage, label[:94].rstrip(" ."), file_stamp(stage)[:2])

    def _check(self) -> None:
        check_local(self.stage)
        if file_stamp(self.stage)[:2] != self.identity or not self.stage.is_dir():
            raise DocForgeError("A pasta temporária do lote mudou.")

    def publish(self, expected_count: int) -> Path:
        self._check()
        if not 1 <= expected_count <= MAX_MEDIA_FILES:
            raise DocForgeError("A quantidade de arquivos do resultado é inválida.")
        files = []
        for path in self.stage.iterdir():
            check_local(path)
            if (
                not path.is_file()
                or path.suffix not in OUTPUT_EXTENSIONS
                or not path.stat().st_size
            ):
                raise DocForgeError("A pasta de saída contém um arquivo inválido.")
            files.append(path.name)
            if len(files) > expected_count:
                raise DocForgeError("A quantidade de arquivos mudou durante a gravação.")
        if len(files) != expected_count:
            raise DocForgeError("O conjunto de resultados está incompleto.")
        for number in range(1, 1001):
            label = self.label if number == 1 else f"{self.label} ({number})"
            target = self.stage.with_name(label)
            try:
                self._install(target)
            except FileExistsError:
                continue
            return target / files[0] if len(files) == 1 else target
        raise DocForgeError("Escolha outra pasta de saída. Há muitos nomes iguais.")

    def _install(self, target: Path) -> None:
        if os.name == "nt":
            os.rename(self.stage, target)
            return
        # Em POSIX, só é permitido substituir uma pasta reservada pelo próprio lote.
        target.mkdir(exist_ok=False)
        try:
            os.replace(self.stage, target)
        except OSError:
            with suppress(OSError):
                target.rmdir()
            raise

    def cleanup(self) -> None:
        # O Windows pode manter um arquivo em gravação bloqueado por instantes após o kill.
        delays = (0, 0.05, 0.1, 0.25) if os.name == "nt" else (0,)
        for delay in delays:
            if delay:
                sleep(delay)
            try:
                self._check()
                rmtree(self.stage)
                return
            except PermissionError:
                continue
            except (OSError, DocForgeError):
                return
