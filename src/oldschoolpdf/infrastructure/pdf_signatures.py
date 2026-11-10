"""Assinatura PKCS#12 e verificação local, carregadas sob demanda."""

import os
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from uuid import uuid4

from oldschoolpdf.domain.errors import OldSchoolPDFError
from oldschoolpdf.domain.security import SIGNING_VERSION
from oldschoolpdf.infrastructure.local_files import FileStamp, check_local, check_pdf, file_stamp
from oldschoolpdf.infrastructure.pdf_storage import check_stage, open_pdf

MAX_CERT_FILES = 8
MAX_SIGNATURES = 30
MAX_PFX_BYTES = 8 * 1024**2


def _require_dependency() -> None:
    try:
        if version("pyHanko") == SIGNING_VERSION:
            return
    except PackageNotFoundError:
        pass
    raise OldSchoolPDFError("Instale o extra opcional signing para usar a assinatura digital.")


def _certificate_file(path: Path, extensions: set[str], limit: int) -> None:
    check_local(path)
    if (
        path.suffix.casefold() not in extensions
        or not path.is_file()
        or not 0 < path.stat().st_size <= limit
    ):
        raise OldSchoolPDFError(
            "Selecione um arquivo local de certificado com formato e tamanho válidos."
        )


def signature_report(
    path: Path, trust_paths: list[str], *, expected: FileStamp | None = None
) -> list[dict]:
    _require_dependency()
    from pyhanko.keys import load_certs_from_pemder
    from pyhanko.pdf_utils.reader import PdfFileReader
    from pyhanko.sign.validation import validate_pdf_signature
    from pyhanko_certvalidator import ValidationContext

    check_pdf(path)
    stamp = file_stamp(path) if expected is None else expected
    if len(trust_paths) > MAX_CERT_FILES:
        raise OldSchoolPDFError("Escolha até oito arquivos de certificados de confiança.")
    for name in trust_paths:
        _certificate_file(Path(name), {".pem", ".crt", ".cer", ".der"}, 512 * 1024)
    try:
        roots = list(load_certs_from_pemder(trust_paths))
        if trust_paths and not roots:
            raise ValueError("Sem certificado X.509")
    except (OSError, ValueError, TypeError):
        raise OldSchoolPDFError(
            "Um dos arquivos de confiança não contém certificado X.509 legível."
        ) from None
    context = ValidationContext(
        trust_roots=roots, allow_fetching=False, revocation_mode="soft-fail"
    )
    reports = []
    try:
        with path.open("rb") as stream:
            if file_stamp(stream.fileno()) != stamp:
                raise OldSchoolPDFError("O arquivo mudou antes da verificação.")
            reader = PdfFileReader(stream, strict=True)
            signatures = reader.embedded_signatures
            if len(signatures) > MAX_SIGNATURES:
                raise OldSchoolPDFError("A verificação está limitada a 30 assinaturas por PDF.")
            for signature in signatures:
                label = signature.field_name[:200]
                try:
                    status = validate_pdf_signature(
                        signature,
                        signer_validation_context=context,
                        ts_validation_context=context,
                    )
                    certificate = signature.signer_cert
                    subject = certificate.subject.native
                    name = subject.get("common_name") or subject.get("organization_name")
                    reports.append(
                        {
                            "field": label,
                            "signer": str(name)[:300] if name else "Consulte a impressão digital",
                            "fingerprint": certificate.sha256.hex(),
                            "intact": status.intact,
                            "valid": status.valid,
                            "trusted": status.trusted,
                            "coverage": status.coverage.name,
                        }
                    )
                except Exception:
                    reports.append({"field": label, "error": "Formato de assinatura incompatível."})
    except OldSchoolPDFError:
        raise
    except Exception:
        raise OldSchoolPDFError("A estrutura de assinatura deste PDF não pôde ser lida.") from None
    check_local(path)
    if file_stamp(path) != stamp:
        raise OldSchoolPDFError("O arquivo mudou durante a verificação.")
    return reports


def sign_copy(
    source: Path, stage: Path, pfx: str, passphrase: str, count: int, *, expected: FileStamp
) -> str:
    _require_dependency()
    from pyhanko.pdf_utils.incremental_writer import IncrementalPdfFileWriter
    from pyhanko.pdf_utils.metadata.xmp_xml import XmpXmlProcessingError
    from pyhanko.sign import signers
    from pyhanko.sign.fields import SigFieldSpec, SigSeedSubFilter

    path = Path(pfx)
    _certificate_file(path, {".pfx", ".p12"}, MAX_PFX_BYTES)
    try:
        with path.open("rb") as certificate:
            data = certificate.read(MAX_PFX_BYTES + 1)
        signer = (
            signers.SimpleSigner.load_pkcs12_data(
                data, (), passphrase=passphrase.encode() if passphrase else None
            )
            if len(data) <= MAX_PFX_BYTES
            else None
        )
    except (OSError, ValueError, TypeError):
        signer = None
    if not signer:
        raise OldSchoolPDFError("O arquivo PKCS#12 ou a senha do certificado é inválida.")
    check_pdf(source)
    check_stage(stage)
    name = "OldSchoolPDF_" + uuid4().hex
    try:
        with source.open("rb") as original, stage.open("r+b") as target:
            if file_stamp(original.fileno()) != expected:
                raise OldSchoolPDFError("O PDF de origem mudou antes da assinatura.")
            metadata = signers.PdfSignatureMetadata(
                field_name=name,
                md_algorithm="sha256",
                subfilter=SigSeedSubFilter.ADOBE_PKCS7_DETACHED,
            )
            signers.sign_pdf(
                IncrementalPdfFileWriter(original, strict=True),
                metadata,
                signer,
                new_field_spec=SigFieldSpec(name),
                output=target,
            )
            target.flush()
            os.fsync(target.fileno())
    except OldSchoolPDFError:
        raise
    except XmpXmlProcessingError:
        raise OldSchoolPDFError(
            "O PDF contém metadados XMP incompatíveis com a assinatura."
        ) from None
    except Exception:
        raise OldSchoolPDFError(
            "Não foi possível assinar este PDF com o certificado escolhido."
        ) from None
    check_local(source)
    if file_stamp(source) != expected:
        raise OldSchoolPDFError("O PDF de origem mudou durante a assinatura.")
    reports = signature_report(stage, [])
    if not any(
        entry.get("field") == name
        and entry.get("valid")
        and entry.get("intact")
        and entry.get("coverage") == "ENTIRE_FILE"
        for entry in reports
    ):
        raise OldSchoolPDFError("A assinatura criada não passou na verificação de integridade.")
    with open_pdf(stage) as result:
        if result.is_repaired or result.page_count != count:
            raise OldSchoolPDFError("A cópia assinada não preservou a estrutura esperada.")
        result.load_page(0)
    return "Assinatura criptográfica conferida · cobertura do arquivo completo"
