"""Estado inicial de documentos; não abre nem modifica arquivos."""

from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Protocol
from uuid import UUID, uuid4


class SignatureState(StrEnum):
    UNKNOWN = "unknown"
    UNSIGNED = "unsigned"
    SIGNED = "signed"


class EditCommand(Protocol):
    """Contrato futuro de undo/redo; operações concretas chegam após M0."""

    description: str

    def execute(self) -> None: ...

    def undo(self) -> None: ...


@dataclass(frozen=True, slots=True)
class PageReference:
    source_index: int
    rotation: int = 0

    def __post_init__(self) -> None:
        if self.source_index < 0 or self.rotation not in (0, 90, 180, 270):
            raise ValueError("Página ou rotação inválida.")


@dataclass(slots=True)
class DocumentSession:
    source_path: Path
    working_copy: Path | None = None
    session_id: UUID = field(default_factory=uuid4)
    dirty: bool = False
    page_map: list[PageReference] = field(default_factory=list)
    zoom: float = 1.0
    selection: tuple[int, ...] = ()
    undo_stack: list[EditCommand] = field(default_factory=list, repr=False)
    redo_stack: list[EditCommand] = field(default_factory=list, repr=False)
    signature_state: SignatureState = SignatureState.UNKNOWN

    def __post_init__(self) -> None:
        if not 0.1 <= self.zoom <= 8.0:
            raise ValueError("Zoom fora do intervalo de 10% a 800%.")
        if self.working_copy and self.source_path.resolve() == self.working_copy.resolve():
            raise ValueError("A cópia de trabalho deve ser diferente do original.")


@dataclass(frozen=True, slots=True)
class DocumentMetadata:
    page_count: int
    title: str = ""
    author: str = ""
    signature_state: SignatureState = SignatureState.UNKNOWN
