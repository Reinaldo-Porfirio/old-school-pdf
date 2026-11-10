"""Inspeção local por adaptador, sem executar ou importar dependências opcionais."""

from dataclasses import dataclass
from typing import Protocol

from docforge.domain.media import OCR_LANGUAGES
from docforge.domain.security import SIGNING_VERSION


class DependencyProbe(Protocol):
    def package_version(self, name: str) -> str | None: ...

    def executable_exists(self, name: str) -> bool: ...


@dataclass(frozen=True, slots=True)
class Capability:
    key: str
    label: str
    detected: bool | None
    implemented: bool
    detail: str
    milestone: str


@dataclass(frozen=True, slots=True)
class CapabilitiesReport:
    items: tuple[Capability, ...]

    def get(self, key: str) -> Capability:
        return next(item for item in self.items if item.key == key)


class CapabilitiesService:
    def __init__(self, probe: DependencyProbe) -> None:
        self.probe = probe
        self.ocr_languages: tuple[str, ...] = ()

    def signing_available(self) -> bool:
        return self.probe.package_version("pyhanko") == SIGNING_VERSION

    def check(self) -> CapabilitiesReport:
        pdf = self.probe.package_version("pymupdf")
        ocr = self.probe.package_version("ocrmypdf")
        signing = self.probe.package_version("pyhanko")
        office = self.probe.executable_exists("soffice") or self.probe.executable_exists(
            "libreoffice"
        )
        return CapabilitiesReport(
            (
                Capability("desktop", "Interface desktop", True, True, "Qt Widgets local", "M0"),
                Capability(
                    "pdf",
                    "Motor PyMuPDF",
                    bool(pdf),
                    True,
                    f"Versão {pdf} · PDF, conversão e otimização" if pdf else "Não instalado",
                    "M4",
                ),
                Capability(
                    "tesseract",
                    "Tesseract integrado",
                    bool(self.ocr_languages),
                    True,
                    "Modelos validados · "
                    + ", ".join(OCR_LANGUAGES[code] for code in self.ocr_languages)
                    if self.ocr_languages
                    else "Valide por.traineddata ou eng.traineddata em OCR > Configurar OCR local.",
                    "M4",
                ),
                Capability(
                    "ocr",
                    "OCRmyPDF",
                    bool(ocr),
                    False,
                    f"Versão detectada {ocr}. O M4 usa Tesseract integrado."
                    if ocr
                    else "Integração externa opcional. O M4 usa Tesseract integrado.",
                    "M4",
                ),
                Capability(
                    "office",
                    "LibreOffice",
                    office,
                    False,
                    "Localizado no PATH; versão não validada"
                    if office
                    else "Não localizado no PATH",
                    "M4",
                ),
                Capability(
                    "signing",
                    "pyHanko",
                    bool(signing),
                    signing == SIGNING_VERSION,
                    f"Versão {signing} · assinatura e verificação locais"
                    if signing == SIGNING_VERSION
                    else f"Instale o extra signing para usar a versão {SIGNING_VERSION}.",
                    "M5",
                ),
                Capability(
                    "certificates",
                    "Certificados digitais",
                    None,
                    signing == SIGNING_VERSION,
                    "Arquivos locais escolhidos sob demanda. Confiança avaliada com raízes locais.",
                    "M5",
                ),
            )
        )
