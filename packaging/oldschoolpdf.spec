# Especificação do PyInstaller para o Old School PDF (pasta única, sem console).
# Rode pelo packaging/build.py, que gera o ícone e o arquivo de versão antes.

from pathlib import Path

from PyInstaller.utils.hooks import copy_metadata

root = Path(SPECPATH).parent
assets = root / "build" / "assets"

a = Analysis(
    [str(root / "packaging" / "launcher.py")],
    pathex=[str(root / "src")],
    datas=[
        (str(root / "LICENSE"), "."),
        (str(root / "THIRD_PARTY_NOTICES.md"), "."),
        # A página de recursos locais lê a versão destes pacotes pelos metadados.
        *copy_metadata("pymupdf"),
        *copy_metadata("pyhanko"),
    ],
    # O leitor é importado sob demanda; declarar garante que entre no pacote.
    hiddenimports=["oldschoolpdf.infrastructure.pdf_worker"],
    excludes=["tkinter", "unittest", "pydoc", "pytest", "PyInstaller", "pymupdf.layout"],
    noarchive=False,
)


def keep(entry) -> bool:
    # Fora do pacote: modelos de IA de layout e arquivos de desenvolvimento do PyMuPDF,
    # OpenGL por software e traduções do Qt além do português do Brasil.
    target = entry[0].replace("\\", "/")
    if target.startswith(("pymupdf/layout/", "pymupdf/mupdf-devel/")):
        return False
    if target.endswith("opengl32sw.dll"):
        return False
    if target.startswith("PySide6/translations/"):
        return target.endswith(("qtbase_pt_BR.qm", "qt_pt_BR.qm"))
    return True


a.datas = [entry for entry in a.datas if keep(entry)]
a.binaries = [entry for entry in a.binaries if keep(entry)]
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="OldSchoolPDF",
    console=False,
    icon=str(assets / "oldschoolpdf.ico"),
    version=str(assets / "version_info.txt"),
    upx=False,
)
coll = COLLECT(exe, a.binaries, a.datas, name="OldSchoolPDF", upx=False)
