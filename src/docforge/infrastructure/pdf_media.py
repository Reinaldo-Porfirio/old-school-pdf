"""Conversão, extração e otimização com saída local e verificada por entrada."""

import os
from collections.abc import Callable
from contextlib import contextmanager
from pathlib import Path

import pymupdf as pdf

from docforge.domain.editing import parse_intervals
from docforge.domain.errors import DocForgeError
from docforge.domain.media import IMAGE_EXTENSIONS, MediaOperation, MediaOptions
from docforge.infrastructure.local_files import check_local, file_stamp
from docforge.infrastructure.media_output import MAX_MEDIA_FILES
from docforge.infrastructure.pdf_editing import indices, select_pages
from docforge.infrastructure.pdf_ocr import MAX_MEDIA_PIXELS, raster, searchable_pdf
from docforge.infrastructure.pdf_storage import (
    MAX_PAGES,
    ensure_signature_ack,
    inspect_inputs,
    merge,
    open_pdf,
    save_validated,
)

Progress = Callable[[int, int, str], None]
MAX_IMAGE_BYTES = 64 * 1024**2
MAX_TEXT_BYTES = 64 * 1024**2


@contextmanager
def plain_pdf(path: Path):
    try:
        document = open_pdf(path)
    except pdf.FileDataError:
        raise DocForgeError("O PDF está corrompido ou usa uma estrutura incompatível.") from None
    with document:
        if document.is_encrypted or (document.metadata or {}).get("encryption"):
            raise DocForgeError("O processamento em lote aceita PDFs sem criptografia.")
        if not 0 < document.page_count <= MAX_PAGES:
            raise DocForgeError("O número de páginas excede os limites do aplicativo.")
        yield document


def _new_pdf(stage: Path, name: str = "documento.pdf") -> Path:
    target = stage / name
    target.touch(exist_ok=False)
    return target


def _image_bytes(path: Path) -> bytes:
    suffix = path.suffix.casefold()
    if suffix not in IMAGE_EXTENSIONS:
        raise DocForgeError("Use arquivos PNG, JPEG ou TIFF.")
    with path.open("rb") as stream:
        data = stream.read(MAX_IMAGE_BYTES + 1)
    signatures = {
        ".png": (b"\x89PNG\r\n\x1a\n",),
        ".jpg": (b"\xff\xd8\xff",),
        ".jpeg": (b"\xff\xd8\xff",),
        ".tif": (b"II*\x00", b"MM\x00*"),
        ".tiff": (b"II*\x00", b"MM\x00*"),
    }
    if len(data) > MAX_IMAGE_BYTES or not data.startswith(signatures[suffix]):
        raise DocForgeError("A imagem tem formato inválido ou excede 64 MiB.")
    return data


def _images_pdf(inputs: tuple[Path, ...], stage: Path, progress: Progress) -> str:
    with pdf.open() as result:
        for index, source in enumerate(inputs):
            progress(index, len(inputs), f"Importando imagem {index + 1} de {len(inputs)}")
            data = _image_bytes(source)
            image = pdf.mupdf.fz_new_image_from_buffer(
                pdf.mupdf.fz_new_buffer_from_copied_data(data)
            )
            if not 0 < image.w() * image.h() <= MAX_MEDIA_PIXELS:
                raise DocForgeError("Uma das imagens excede o limite de 26 milhões de pixels.")
            with pdf.open(stream=data, filetype=source.suffix[1:].casefold()) as image_doc:
                if not 0 < image_doc.page_count <= MAX_MEDIA_FILES - result.page_count:
                    raise DocForgeError("O conjunto de imagens excede 2.000 páginas.")
                with pdf.open(stream=image_doc.convert_to_pdf(), filetype="pdf") as part:
                    result.insert_pdf(part)
        progress(len(inputs), len(inputs), "Validando o PDF de imagens")
        save_validated(result, _new_pdf(stage), None)
        return f"{result.page_count} página(s) na ordem da lista de imagens"


def _render_images(
    document: pdf.Document, pages: list[int], stage: Path, options: MediaOptions, progress: Progress
) -> str:
    if len(pages) > MAX_MEDIA_FILES:
        raise DocForgeError("Escolha até 2.000 páginas por exportação de imagens.")
    for index, page in enumerate(pages):
        progress(index, len(pages), f"Renderizando página {page + 1}")
        target = stage / f"pagina-{page + 1:05d}.{options.image_format}"
        pixmap = raster(document[page], options.dpi)
        with target.open("xb") as output:
            output.write(pixmap.tobytes(options.image_format, jpg_quality=90))
    return f"{len(pages)} imagem(ns) · {options.dpi} DPI · {options.image_format.upper()}"


def _text(document: pdf.Document, pages: list[int], stage: Path, progress: Progress) -> str:
    written = available = 0
    with (stage / "texto.txt").open("xb") as output:
        for index, page in enumerate(pages):
            progress(index, len(pages), f"Extraindo texto da página {page + 1}")
            text = document[page].get_text(sort=True).strip()
            available += bool(text)
            block = f"--- Página {page + 1} ---\n{text}\n\n".encode()
            written += len(block)
            if written > MAX_TEXT_BYTES:
                raise DocForgeError("O texto extraído excede o limite de 64 MiB.")
            output.write(block)
    if not available:
        raise DocForgeError("A seleção não contém texto extraível. Digitalizações exigem OCR.")
    return f"UTF-8 · {available} página(s) com texto · sem formatação do PDF"


def _image_content(document: pdf.Document, xref: int, mask: int) -> tuple[str, bytes]:
    image = document.extract_image(xref)
    if not image or not 0 < image["width"] * image["height"] <= MAX_MEDIA_PIXELS:
        raise DocForgeError("Uma imagem incorporada é inválida ou excede 26 milhões de pixels.")
    if not mask and image["ext"] in {"png", "jpeg"}:
        return "jpg" if image["ext"] == "jpeg" else "png", image["image"]
    pixmap = pdf.Pixmap(document, xref)
    if pixmap.colorspace and pixmap.colorspace.n > 3:
        pixmap = pdf.Pixmap(pdf.csRGB, pixmap)
    if mask:
        pixmap = pdf.Pixmap(pixmap, pdf.Pixmap(document, mask))
    return "png", pixmap.tobytes("png")


def _extract_images(
    document: pdf.Document, pages: list[int], stage: Path, progress: Progress
) -> str:
    seen = set()
    for index, page in enumerate(pages):
        progress(index, len(pages), f"Procurando imagens na página {page + 1}")
        for xref, mask, *_ in document[page].get_images():
            if not xref or xref in seen:
                continue
            if len(seen) == MAX_MEDIA_FILES:
                raise DocForgeError("A extração excede o limite de 2.000 imagens.")
            seen.add(xref)
            suffix, content = _image_content(document, xref, mask)
            with (stage / f"imagem-{len(seen):05d}.{suffix}").open("xb") as output:
                output.write(content)
    if not seen:
        raise DocForgeError("A seleção não contém imagens incorporadas disponíveis.")
    return f"{len(seen)} imagem(ns) incorporada(s), sem duplicar objetos compartilhados"


def _optimize(
    document: pdf.Document, source: Path, stage: Path, options: MediaOptions, progress: Progress
) -> str:
    before = source.stat().st_size
    if options.reduce_images:
        progress(0, 2, "Recomprimindo imagens. Referência de resolução: 150 DPI")
        document.rewrite_images(dpi_threshold=180, dpi_target=150, quality=82, bitonal=False)
    progress(1, 2, "Compactando e validando o PDF")
    target = _new_pdf(stage)
    save_validated(document, target, None, compact=True)
    after = target.stat().st_size
    sizes = f"{before:,} → {after:,} bytes".replace(",", ".")
    if after >= before:
        target.unlink()
        return f"{sizes} · sem redução, nenhuma cópia publicada"
    savings = f"{1 - after / before:.1%}".replace(".", ",")
    method = "recompressão de imagens" if options.reduce_images else "compactação estrutural"
    return f"{sizes} · economia de {savings} · {method}"


def _split(source: Path, count: int, stage: Path, options: MediaOptions, progress: Progress) -> str:
    size = options.split_size
    parts = (count + size - 1) // size
    if parts > MAX_MEDIA_FILES:
        raise DocForgeError("A divisão excede o limite de 2.000 partes por PDF.")
    for index, start in enumerate(range(0, count, size)):
        progress(index, parts, f"Preparando parte {index + 1} de {parts}")
        with plain_pdf(source) as part:
            ensure_signature_ack(part, options.confirmed)
            select_pages(part, list(range(start, min(count, start + size))))
            save_validated(part, _new_pdf(stage, f"parte-{index + 1:05d}.pdf"), None)
    return f"{count} página(s) em {parts} PDF(s)"


def _process_pdf(
    operation: MediaOperation, source: Path, stage: Path, options: MediaOptions, progress: Progress
) -> str:
    with plain_pdf(source) as document:
        if operation in {MediaOperation.OCR, MediaOperation.SPLIT, MediaOperation.OPTIMIZE}:
            ensure_signature_ack(document, options.confirmed)
        count = document.page_count
        if operation == MediaOperation.SPLIT:
            return _split(source, count, stage, options, progress)
        if operation == MediaOperation.OPTIMIZE:
            return _optimize(document, source, stage, options, progress)
        pages = (
            indices(parse_intervals(options.ranges, count), count)
            if options.ranges
            else list(range(count))
        )
        if operation == MediaOperation.OCR:
            return searchable_pdf(
                document,
                pages,
                _new_pdf(stage),
                dpi=options.dpi,
                language=options.language,
                tessdata=options.tessdata,
                progress=progress,
            )
        if operation == MediaOperation.RENDER:
            return _render_images(document, pages, stage, options, progress)
        if operation == MediaOperation.TEXT:
            return _text(document, pages, stage, progress)
        return _extract_images(document, pages, stage, progress)


def process_media(
    operation: str, inputs: list[str], stage: str, options: dict, progress: Progress
) -> dict:
    mode = MediaOperation(operation)
    parameters = MediaOptions(**options)
    destination = Path(stage)
    check_local(destination)
    if any(destination.iterdir()):
        raise DocForgeError("A pasta temporária do lote precisa estar vazia.")
    sources = tuple(Path(path) for path in inputs)
    for source in sources:
        check_local(source)
        if not source.is_file():
            raise DocForgeError("O lote aceita apenas arquivos locais regulares.")
    originals = tuple(file_stamp(source) for source in sources)
    if mode == MediaOperation.IMAGES_PDF:
        detail = _images_pdf(sources, destination, progress)
    elif mode == MediaOperation.MERGE:
        progress(0, 2, "Conferindo os PDFs para mesclagem")
        inspected = inspect_inputs(inputs)["items"]
        records = [{"path": path, **item} for path, item in zip(inputs, inspected, strict=True)]
        progress(1, 2, "Mesclando e validando páginas")
        merged = merge(records, str(_new_pdf(destination)), parameters.confirmed)
        detail = f"{merged['page_count']} página(s) em um PDF"
    else:
        detail = _process_pdf(mode, sources[0], destination, parameters, progress)
    for source, previous in zip(sources, originals, strict=True):
        check_local(source)
        if file_stamp(source) != previous:
            raise DocForgeError(
                "Um arquivo de entrada mudou durante a tarefa. Selecione-o novamente."
            )
    results = list(destination.iterdir())
    for path in results:
        with path.open("r+b") as output:
            os.fsync(output.fileno())
    return {"files": len(results), "detail": detail}
