"""Limites, opções e valores das operações de segurança local."""

from dataclasses import dataclass

from oldschoolpdf.domain.errors import OldSchoolPDFError
from oldschoolpdf.domain.viewer import PdfRect

METADATA_FIELDS = {
    "title": "Título",
    "author": "Autor",
    "subject": "Assunto",
    "keywords": "Palavras-chave",
    "creator": "Aplicativo de origem",
    "producer": "Produtor do PDF",
    "creationDate": "Data de criação",
    "modDate": "Data de modificação",
    "trapped": "Marca de impressão",
}
PERMISSION_LABELS = {
    "print": "Imprimir",
    "copy": "Copiar texto e imagens",
    "modify": "Modificar conteúdo",
    "annotate": "Adicionar e modificar anotações",
    "form": "Preencher formulários",
    "assemble": "Organizar páginas",
}
SIGNING_VERSION = "0.38.1"
SIGNATURE_PAD_SIZE = (480, 160)
REDACTION_DPI = 150
MAX_REDACTION_PAGES = 100
MAX_REDACTION_AREAS = 100
MAX_REDACTION_PIXELS = 100_000_000


def validate_passwords(user: str, owner: str) -> None:
    for password in (user, owner):
        if (
            not password.strip()
            or len(password) > 40
            or len(password.encode()) > 127
            or any(ord(character) < 32 or ord(character) == 127 for character in password)
        ):
            raise OldSchoolPDFError("Use senhas de 1 a 40 caracteres, sem caracteres de controle.")
    if user == owner:
        raise OldSchoolPDFError("As senhas de abertura e de proprietário devem ser diferentes.")


@dataclass(frozen=True, slots=True)
class RedactionArea:
    page: int
    region: PdfRect

    def __post_init__(self) -> None:
        x0, y0, x1, y1 = self.region
        if self.page < 0 or not (0 <= x0 < x1 <= 1 and 0 <= y0 < y1 <= 1):
            raise OldSchoolPDFError("Uma área de redação está fora da página.")
