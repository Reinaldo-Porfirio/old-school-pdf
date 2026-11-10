"""Gera o executável e o instalador do Old School PDF no Windows.

Uso, na raiz do projeto:
    uv run --no-sync python packaging/build.py [--sem-instalador]

Etapas: ícone e imagens, arquivo de versão, PyInstaller, teste de abertura do
executável e, se o Inno Setup 6 estiver instalado, o instalador em dist/.
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "build" / "assets"
APP_DIR = ROOT / "dist" / "pyinstaller" / "OldSchoolPDF"
EXE = APP_DIR / "OldSchoolPDF.exe"

sys.path.insert(0, str(ROOT / "src"))
from oldschoolpdf import __version__  # noqa: E402

VERSION_INFO = """VSVersionInfo(
  ffi=FixedFileInfo(filevers=({v}, 0), prodvers=({v}, 0), mask=0x3f, flags=0x0,
                    OS=0x40004, fileType=0x1, subtype=0x0, date=(0, 0)),
  kids=[
    StringFileInfo([StringTable('041604b0', [
      StringStruct('CompanyName', 'Old School PDF'),
      StringStruct('FileDescription', 'Old School PDF'),
      StringStruct('FileVersion', '{dotted}'),
      StringStruct('InternalName', 'OldSchoolPDF'),
      StringStruct('LegalCopyright', 'AGPL-3.0-or-later'),
      StringStruct('OriginalFilename', 'OldSchoolPDF.exe'),
      StringStruct('ProductName', 'Old School PDF'),
      StringStruct('ProductVersion', '{dotted}')])]),
    VarFileInfo([VarStruct('Translation', [0x0416, 1200])])
  ]
)
"""


def step(title: str) -> None:
    print(f"\n=== {title} ===", flush=True)


def run(*command: str | Path) -> None:
    subprocess.run([str(part) for part in command], cwd=ROOT, check=True)


def write_version_info() -> None:
    parts = [int(piece) for piece in __version__.split(".")[:3]]
    numbers = ", ".join(str(n) for n in parts)
    text = VERSION_INFO.format(v=numbers, dotted=".".join(map(str, parts)) + ".0")
    (ASSETS / "version_info.txt").write_text(text, encoding="utf-8")


def smoke_test_executable() -> None:
    with tempfile.TemporaryDirectory(prefix="oldschoolpdf-exe-") as scratch:
        settings = Path(scratch) / "settings.ini"
        result = subprocess.run(
            [str(EXE), "--settings-file", str(settings), "--smoke-test"], timeout=240
        )
        if result.returncode != 0 or not settings.exists():
            raise SystemExit("O executável não abriu e fechou corretamente.")
    print("Executável abriu, gravou preferências e fechou.")


def test_frozen_worker() -> None:
    # Fala com o leitor empacotado pelo mesmo protocolo de pipes usado pelo aplicativo.
    import pymupdf

    from oldschoolpdf.infrastructure.pdf_worker import FRAME, WORKER_FLAG

    with tempfile.TemporaryDirectory(prefix="oldschoolpdf-worker-") as scratch:
        pdf = Path(scratch) / "teste de leitura.pdf"
        document = pymupdf.open()
        document.new_page().insert_text((72, 72), "Old School PDF empacotado", fontsize=14)
        document.save(pdf)
        document.close()
        worker = subprocess.Popen(
            [str(EXE), WORKER_FLAG], stdin=subprocess.PIPE, stdout=subprocess.PIPE
        )

        def ask(operation: str, **arguments) -> tuple[dict, bytes]:
            message = json.dumps({"op": operation, "args": arguments}) + "\n"
            worker.stdin.write(message.encode())
            worker.stdin.flush()
            size, length = FRAME.unpack(worker.stdout.read(FRAME.size))
            return json.loads(worker.stdout.read(size)), worker.stdout.read(length)

        try:
            opened, _ = ask("open", path=str(pdf))
            frame, pixels = ask(
                "render", page=0, rotation=0, zoom="page", width=400, height=500, dpr=1.0
            )
            found, _ = ask("search", page=0, query="empacotado", limit=10)
            # Carrega pyHanko e lxml dentro do executável.
            signatures, _ = ask("verify_signatures", trust_paths=[])
        finally:
            worker.stdin.close()
            worker.wait(timeout=30)
        problems = [
            reply["error"] for reply in (opened, frame, found, signatures) if "error" in reply
        ]
        if problems or not pixels:
            raise SystemExit(f"O leitor empacotado falhou: {problems or 'imagem vazia'}")
    print("Leitor empacotado abriu, renderizou, pesquisou e verificou assinaturas.")
    bundled = {path.name.split("-")[0].lower() for path in APP_DIR.glob("_internal/*.dist-info")}
    if missing := {"pymupdf", "pyhanko"} - bundled:
        raise SystemExit(f"Metadados ausentes no pacote: {sorted(missing)}")


def find_iscc() -> Path | None:
    candidates = [shutil.which("ISCC")]
    for base in (os.environ.get("PROGRAMFILES(X86)"), os.environ.get("PROGRAMFILES")):
        if base:
            candidates.append(str(Path(base) / "Inno Setup 6" / "ISCC.exe"))
    if local := os.environ.get("LOCALAPPDATA"):
        candidates.append(str(Path(local) / "Programs" / "Inno Setup 6" / "ISCC.exe"))
    return next((Path(c) for c in candidates if c and Path(c).exists()), None)


def main() -> None:
    step(f"Old School PDF {__version__}")
    ASSETS.mkdir(parents=True, exist_ok=True)

    step("Ícone e imagens do assistente")
    run(sys.executable, "packaging/make_assets.py", ASSETS)
    write_version_info()

    step("PyInstaller")
    run(
        sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean",
        "--distpath", ROOT / "dist" / "pyinstaller",
        "--workpath", ROOT / "build" / "pyinstaller",
        "packaging/oldschoolpdf.spec",
    )  # fmt: skip

    step("Teste do executável")
    smoke_test_executable()
    test_frozen_worker()

    if "--sem-instalador" in sys.argv:
        return
    step("Instalador")
    iscc = find_iscc()
    if iscc is None:
        print("Inno Setup 6 não encontrado. O executável está em", APP_DIR)
        print("Instale com: winget install JRSoftware.InnoSetup")
        return
    run(
        iscc, "/Qp",
        f"/DAppVersion={__version__}",
        f"/DSourceDir={APP_DIR}",
        f"/DAssetsDir={ASSETS}",
        f"/DRootDir={ROOT}",
        f"/O{ROOT / 'dist'}",
        "packaging/installer.iss",
    )  # fmt: skip
    print("\nInstalador:", ROOT / "dist" / f"OldSchoolPDF-{__version__}-setup.exe")


if __name__ == "__main__":
    main()
