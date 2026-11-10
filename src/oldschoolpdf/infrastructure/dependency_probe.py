"""Só metadados e PATH: nenhum subprocesso, import de motor ou consulta de rede."""

from importlib.metadata import PackageNotFoundError, version
from shutil import which


class LocalDependencyProbe:
    def package_version(self, name: str) -> str | None:
        try:
            return version(name)
        except PackageNotFoundError:
            return None

    def executable_exists(self, name: str) -> bool:
        return which(name) is not None
