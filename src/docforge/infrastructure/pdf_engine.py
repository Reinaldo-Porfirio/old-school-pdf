"""Leitura e edição do PyMuPDF no processo de um documento."""

import math
from bisect import bisect_right
from collections.abc import Callable
from pathlib import Path
from unicodedata import normalize

import pymupdf

from docforge.domain.editing import ANNOTATION_EDITS, PAGE_EDITS
from docforge.domain.errors import DocForgeError
from docforge.domain.viewer import MAX_QUERY_LENGTH, MAX_RASTER_BYTES, MAX_SEARCH_HITS, PdfRect
from docforge.infrastructure.local_files import FileStamp, file_stamp
from docforge.infrastructure.pdf_editing import (
    edit_annotation,
    edit_pages,
    indices,
    normalized_rect,
    page_rect,
    read_objects,
    select_pages,
    update_field,
)
from docforge.infrastructure.pdf_security import (
    encrypt_copy,
    protected,
    redact_copy,
    require_owner,
    strip_metadata,
)
from docforge.infrastructure.pdf_signatures import sign_copy, signature_report
from docforge.infrastructure.pdf_storage import (
    MAX_PAGES,
    PdfHistory,
    Revision,
    ensure_signature_ack,
    has_signature,
    has_xfa,
    open_pdf,
    save_validated,
)

MAX_PAGE_POINTS = 25_000
MAX_WORDS = 120_000
MAX_COPY_LENGTH = 128_000


def _fold(text: str) -> str:
    return normalize("NFKC", text).casefold()


class PdfEngine:
    def __init__(self) -> None:
        pymupdf.use_layout(False)
        pymupdf.TOOLS.mupdf_display_errors(False)
        pymupdf.TOOLS.mupdf_display_warnings(False)
        self.document: pymupdf.Document | None = None
        self.owner_authenticated = False
        self.history: PdfHistory | None = None
        self._password: str | None = None

    def close(self) -> None:
        if self.document is not None:
            self.document.close()
            self.document = None
        self._password = None
        self.history = None

    def open(self, path: str) -> dict:
        self.close()
        self.owner_authenticated = False
        try:
            file_path = Path(path)
            self.document = open_pdf(file_path)
            self.history = PdfHistory(file_path)
        except FileNotFoundError:
            raise DocForgeError("O arquivo PDF não foi encontrado.") from None
        except PermissionError:
            raise DocForgeError("O aplicativo não tem permissão para ler este PDF.") from None
        except (OSError, ValueError):
            raise DocForgeError("Não foi possível ler o arquivo PDF selecionado.") from None
        except pymupdf.FileDataError:
            raise DocForgeError(
                "O PDF está corrompido ou usa uma estrutura incompatível."
            ) from None
        if not self.document.is_pdf:
            raise DocForgeError("O conteúdo do arquivo não é um PDF.")
        if self.document.is_encrypted:
            return {"state": "password", "incorrect": False}
        return self._metadata()

    def authenticate(self, password: str) -> dict:
        doc = self.document
        if doc is None or not doc.is_encrypted:
            raise DocForgeError("A sessão não está aguardando senha.")
        authorized = doc.authenticate(password)
        if not authorized:
            return {"state": "password", "incorrect": True}
        self.owner_authenticated = bool(authorized & 4)
        self._password = password
        return self._metadata()

    def _copy_allowed(self) -> bool:
        return self._allowed(pymupdf.PDF_PERM_COPY)

    def _allowed(self, permissions: int) -> bool:
        assert self.document is not None
        return self.owner_authenticated or bool(self.document.permissions & permissions)

    def _legacy_permissions(self) -> bool:
        return self.document.xref_get_key(-1, "Encrypt/R") == ("int", "2")

    def _assembly_permission(self) -> int:
        return pymupdf.PDF_PERM_MODIFY if self._legacy_permissions() else pymupdf.PDF_PERM_ASSEMBLE

    def _form_permissions(self) -> int:
        return (
            pymupdf.PDF_PERM_ANNOTATE
            if self._legacy_permissions()
            else pymupdf.PDF_PERM_FORM | pymupdf.PDF_PERM_ANNOTATE
        )

    def _metadata(self) -> dict:
        doc = self.document
        assert doc is not None
        count = doc.page_count
        if count < 1:
            raise DocForgeError("O PDF não contém páginas legíveis.")
        if count > MAX_PAGES:
            raise DocForgeError("Este PDF excede o limite de 100 mil páginas.")
        metadata = doc.metadata or {}
        return {
            "state": "open",
            "page_count": count,
            "title": (metadata.get("title") or "")[:512],
            "author": (metadata.get("author") or "")[:512],
            "format": (metadata.get("format") or "PDF")[:40],
            "protected": bool(metadata.get("encryption")),
            "owner_authenticated": self.owner_authenticated,
            "copy_allowed": self._copy_allowed(),
            "repaired": doc.is_repaired,
            "signed": has_signature(doc),
            "can_organize": self._allowed(self._assembly_permission()),
            "can_annotate": self._allowed(pymupdf.PDF_PERM_ANNOTATE),
            "can_fill": not has_xfa(doc) and self._allowed(self._form_permissions()),
        }

    def _page(self, index: int) -> pymupdf.Page:
        doc = self.document
        if doc is None or doc.is_encrypted or not 0 <= index < doc.page_count:
            raise DocForgeError("Esta página não está disponível.")
        page = doc.load_page(index)
        if not all(0 < value <= MAX_PAGE_POINTS for value in (page.rect.width, page.rect.height)):
            raise DocForgeError("As dimensões desta página excedem o limite do visualizador.")
        return page

    def render(
        self, page: int, rotation: int, zoom: float | str, width: int, height: int, dpr: float
    ) -> tuple[dict, bytes]:
        pdf_page = self._page(page)
        page_width, page_height = pdf_page.rect.width, pdf_page.rect.height
        if rotation in (90, 270):
            page_width, page_height = page_height, page_width
        if zoom in ("page", "thumbnail", "continuous"):
            scale = min(width / page_width, height / page_height, 8.0)
        elif zoom == "width":
            scale = min(width / page_width, 8.0)
        else:
            scale = float(zoom)
        if not 0 < scale <= 8 or rotation not in (0, 90, 180, 270) or not 1 <= dpr <= 4:
            raise DocForgeError("Parâmetros de visualização inválidos.")
        desired = scale * dpr
        raster_scale = min(
            desired,
            8190 / max(page_width, page_height),
            math.sqrt(7_900_000 / (page_width * page_height)),
        )
        matrix = pymupdf.Matrix(raster_scale, raster_scale).prerotate(rotation)
        raster = pdf_page.get_pixmap(matrix=matrix, colorspace=pymupdf.csRGB, alpha=False)
        if raster.stride * raster.height > MAX_RASTER_BYTES:
            raise DocForgeError("A imagem da página excede o limite de memória.")
        return {
            "page": page,
            "width": raster.width,
            "height": raster.height,
            "stride": raster.stride,
            "width_pt": page_width,
            "height_pt": page_height,
            "rotation": (pdf_page.rotation + rotation) % 360,
            "scale": scale,
            "limited": raster_scale < desired,
        }, raster.samples

    def search(self, page: int, query: str, limit: int) -> dict:
        pdf_page = self._page(page)
        needle = _fold(" ".join(query.split()))
        if not needle or len(query) > MAX_QUERY_LENGTH or not 1 <= limit <= MAX_SEARCH_HITS:
            raise DocForgeError("A consulta de busca é inválida.")
        # As coordenadas dos termos são anteriores à rotação da página.
        words = pdf_page.get_text("words", sort=pdf_page.rotation == 0)
        if len(words) > MAX_WORDS:
            raise DocForgeError("Uma página excedeu o limite de texto da busca.")
        tokens = [_fold(word[4]) for word in words]
        offsets = []
        offset = 0
        for token in tokens:
            offsets.append(offset)
            offset += len(token) + 1
        haystack = " ".join(tokens)
        hits = []
        cursor = 0
        while len(hits) < limit:
            position = haystack.find(needle, cursor)
            if position < 0:
                break
            cursor = position + len(needle)
            first = bisect_right(offsets, position) - 1
            stop = bisect_right(offsets, cursor - 1)
            lines = {}
            for word in words[first:stop]:
                key = (word[5], word[6])
                bounds = pymupdf.Rect(word[:4])
                lines[key] = lines[key] | bounds if key in lines else bounds
            hits.append([normalized_rect(pdf_page, bounds) for bounds in lines.values()])
        return {"hits": hits, "has_more": haystack.find(needle, cursor) >= 0}

    def extract(self, page: int, region: PdfRect | None) -> dict:
        pdf_page = self._page(page)
        if not self._copy_allowed():
            raise DocForgeError("Este PDF restringe a cópia de texto.")
        clip = page_rect(pdf_page, region) if region is not None else None
        text = pdf_page.get_text("text", clip=clip, sort=True)
        if len(text) > MAX_COPY_LENGTH:
            raise DocForgeError("O texto é muito longo para uma cópia. Selecione uma área menor.")
        return {"text": text}

    def objects(self, page: int) -> dict:
        return read_objects(self._page(page))

    def _revision_result(self) -> dict:
        history = self.history
        return {
            "revision": history.current.serial,
            "working_copy": str(history.current.path) if history.current.serial else None,
            "page": history.current.page,
            "page_count": self.document.page_count,
            "undo": history.position > 0,
            "redo": history.position + 1 < len(history.revisions),
        }

    def edit(self, action: str, page: int, values: dict, scratch: str, confirmed: bool) -> dict:
        self._page(page)
        ensure_signature_ack(self.document, confirmed)
        if action in PAGE_EDITS:
            permission = self._assembly_permission()
        elif action in ANNOTATION_EDITS:
            permission = pymupdf.PDF_PERM_ANNOTATE
        elif action == "fill_field":
            if has_xfa(self.document):
                raise DocForgeError(
                    "Formulários XFA estão disponíveis apenas para leitura passiva."
                )
            permission = self._form_permissions()
        else:
            raise DocForgeError("Operação de edição desconhecida.")
        if not self._allowed(permission):
            raise DocForgeError("As permissões do PDF restringem essa alteração.")
        with self.history.read(self.history.current, self._password) as working:
            if action in PAGE_EDITS:
                page = edit_pages(working, action, page, values)
            elif action == "fill_field":
                update_field(working[page], values)
            else:
                edit_annotation(working[page], action, values)
            verified = self.history.add(working, scratch, self._password, page)
        self.document.close()
        self.document = verified
        return self._revision_result()

    def step(self, direction: int) -> dict:
        verified = self.history.step(direction, self._password)
        self.document.close()
        self.document = verified
        return self._revision_result()

    def export(
        self,
        outputs: list[dict],
        confirmed: bool,
        security: dict | None = None,
        progress: Callable[[int, int, str], None] | None = None,
    ) -> dict:
        ensure_signature_ack(self.document, confirmed)
        revision = self.history.current
        if security is not None:
            if len(outputs) != 1 or outputs[0]["ranges"] is not None:
                raise DocForgeError(
                    "A operação de segurança exige uma saída de documento completo."
                )
            with self.history.read(revision, self._password) as working:
                detail = self._security_copy(
                    revision, working, Path(outputs[0]["stage"]), security, progress
                )
            return {"revision": revision.serial, "detail": detail}
        for output in outputs:
            with self.history.read(revision, self._password) as working:
                if output["ranges"] is not None:
                    if not self._allowed(self._assembly_permission()):
                        raise DocForgeError(
                            "As permissões do PDF restringem a extração de páginas."
                        )
                    select_pages(working, indices(output["ranges"], working.page_count))
                save_validated(working, Path(output["stage"]), self._password)
        return {"revision": revision.serial}

    def _security_copy(
        self,
        revision: Revision,
        working: pymupdf.Document,
        stage: Path,
        security: dict,
        progress: Callable[[int, int, str], None] | None,
    ) -> str:
        action, values = security["action"], security["values"]
        if action in {"metadata", "protect"}:
            require_owner(working, self.owner_authenticated, values.get("current_owner", ""))
            if action == "metadata":
                return strip_metadata(
                    working, stage, self._password, values["fields"], values["xml"]
                )
            return encrypt_copy(working, stage, values["user"], values["owner"], values["allowed"])
        if protected(working):
            raise DocForgeError("Esta operação exige um PDF sem criptografia.")
        if action == "redact":
            return redact_copy(working, stage, values["marks"], progress or (lambda *_: None))
        if action == "sign":
            if has_signature(working) or working.is_repaired:
                raise DocForgeError(
                    "A assinatura exige um PDF íntegro e sem assinaturas anteriores."
                )
            return sign_copy(
                revision.path,
                stage,
                values["pfx"],
                values["passphrase"],
                working.page_count,
                expected=self._revision_stamp(revision),
            )
        raise DocForgeError("Operação de segurança desconhecida.")

    def verify_signatures(self, trust_paths: list[str]) -> dict:
        revision = self.history.current
        with self.history.read(revision, self._password) as working:
            if protected(working):
                raise DocForgeError("A verificação de assinaturas exige um PDF sem criptografia.")
            return {
                "signatures": signature_report(
                    revision.path, trust_paths, expected=self._revision_stamp(revision)
                )
            }

    def _revision_stamp(self, revision: Revision) -> FileStamp:
        return file_stamp(revision.path) if revision.serial else self.history.original_stamp
