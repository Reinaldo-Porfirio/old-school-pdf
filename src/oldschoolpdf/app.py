"""Ponto de composição do desktop e dos serviços PDF locais."""

import argparse
import sys
from pathlib import Path

from PySide6.QtCore import QLibraryInfo, QLocale, QTimer, QTranslator
from PySide6.QtWidgets import QApplication

from oldschoolpdf import __version__
from oldschoolpdf.application.capability_service import CapabilitiesService
from oldschoolpdf.application.job_service import JobRegistry
from oldschoolpdf.application.pdf_viewer import PdfWorkspace
from oldschoolpdf.infrastructure.dependency_probe import LocalDependencyProbe
from oldschoolpdf.infrastructure.pdf_process import PdfProcess
from oldschoolpdf.infrastructure.settings_repository import SettingsRepository
from oldschoolpdf.ui.main_window import MainWindow


def configure_application(app: QApplication) -> None:
    app.setOrganizationName("")
    app.setApplicationName("Old School PDF")
    app.setApplicationVersion(__version__)
    QLocale.setDefault(QLocale(QLocale.Language.Portuguese, QLocale.Country.Brazil))
    # Infraestrutura pronta para QTranslator e catálogos próprios nos próximos idiomas.
    translator = QTranslator(app)
    if translator.load(
        "qtbase_pt_BR", QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath)
    ):
        app.installTranslator(translator)
    app.oldschoolpdf_translator = translator


def create_window(settings_path: Path | None = None) -> MainWindow:
    jobs = JobRegistry()
    return MainWindow(
        settings=SettingsRepository(settings_path),
        capabilities=CapabilitiesService(LocalDependencyProbe()),
        jobs=jobs,
        pdf_workspace=PdfWorkspace(jobs, PdfProcess),
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="oldschoolpdf",
        description="Old School PDF — leitura, edição, OCR e conversão local de PDFs.",
    )
    parser.add_argument("--version", action="version", version=__version__)
    parser.add_argument("--settings-file", type=Path, help="arquivo INI local de preferências")
    parser.add_argument("pdf", nargs="*", type=Path, help="arquivos PDF locais para abrir")
    parser.add_argument(
        "--smoke-test",
        action="store_true",
        help="iniciar a janela, salvar preferências e encerrar após 300 ms (diagnóstico)",
    )
    args = parser.parse_args(argv)
    app = QApplication([sys.argv[0]])
    configure_application(app)
    window = create_window(args.settings_file)
    window.show()
    if args.pdf:
        window.open_pdfs(args.pdf)
    if args.smoke_test:
        QTimer.singleShot(300, window.close)
    return app.exec()
