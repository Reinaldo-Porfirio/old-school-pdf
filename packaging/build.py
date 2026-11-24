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

        def ask(command: str, /, **arguments) -> tuple[dict, bytes]:
            message = json.dumps({"op": command, "args": arguments}) + "\n"
            worker.stdin.write(message.encode())
            worker.stdin.flush()
            while True:
                size, length = FRAME.unpack(worker.stdout.read(FRAME.size))
                header, body = json.loads(worker.stdout.read(size)), worker.stdout.read(length)
                # Conversões em lote mandam quadros de progresso antes da resposta.
                if "progress" not in header:
                    return header, body

        try:
            opened, _ = ask("open", path=str(pdf))
            frame, pixels = ask(
                "render", page=0, rotation=0, zoom="page", width=400, height=500, dpr=1.0
            )
            found, _ = ask("search", page=0, query="empacotado", limit=10)
            # Carrega pyHanko e lxml dentro do executável.
            signatures, _ = ask("verify_signatures", trust_paths=[])
            # Edição de texto: fontes do sistema, verificação e página gêmea no executável.
            blocks, _ = ask("text_blocks", page=0, width=400, height=500, dpr=1.0)
            block = blocks["result"]["blocks"][0] if "result" in blocks else None
            edit = (
                [{"key": block["key"], "runs": [dict(block["runs"][0], text="Editado no .exe")]}]
                if block
                else []
            )
            preview, preview_pixels = ask(
                "preview_text", page=0, blocks=edit, options={}, width=400, height=500, dpr=1.0
            )
            # Marcadores, páginas novas e tamanho do papel (0.9).
            outline, _ = ask("outline")
            work = Path(scratch) / "revisoes"
            work.mkdir()
            blank, _ = ask("edit", action="insert_blank", page=0, values={"size": "a4"},
                           scratch=str(work), confirmed=False)  # fmt: skip
            resized, _ = ask("edit", action="resize_pages", page=0,
                             values={"ranges": [[0, 1]], "size": "letter"},
                             scratch=str(work), confirmed=False)  # fmt: skip
            # Numeração (TextWriter), marca d'água (SVG em contorno) e localizar (0.10).
            numbered, _ = ask("edit", action="header_footer", page=0,
                              values={"ranges": [[0, 1]], "slots": {"footer_center": "[página]"}},
                              scratch=str(work), confirmed=False)  # fmt: skip
            marked, _ = ask("edit", action="watermark", page=0,
                            values={"ranges": [[0, 1]], "mode": "text", "text": "CÓPIA"},
                            scratch=str(work), confirmed=False)  # fmt: skip
            matches, _ = ask("find_text", values={"query": "empacotado", "ranges": [[0, 1]]})
            # Conversão para Word: python-docx e o modelo de documento empacotados.
            word = Path(scratch) / "word"
            word.mkdir()
            converted, _ = ask("process_media", operation="docx", inputs=[str(pdf)],
                               stage=str(word), options={})  # fmt: skip
        finally:
            worker.stdin.close()
            worker.wait(timeout=30)
        problems = [
            reply["error"]
            for reply in (
                opened,
                frame,
                found,
                signatures,
                blocks,
                preview,
                outline,
                blank,
                resized,
                numbered,
                marked,
                matches,
                converted,
            )
            if "error" in reply
        ]
        if problems or not pixels or not preview_pixels:
            raise SystemExit(f"O leitor empacotado falhou: {problems or 'imagem vazia'}")
        if blank["result"]["page_count"] != 2 or not (word / "documento.docx").stat().st_size:
            raise SystemExit("O leitor empacotado não inseriu a página ou não gerou o .docx.")
        if marked["result"]["report"]["pages"] != 2 or not matches["result"]["items"]:
            raise SystemExit("O leitor empacotado não aplicou a marca d'água ou não localizou.")
    print(
        "Leitor empacotado abriu, renderizou, pesquisou, verificou assinaturas, editou texto, "
        "leu marcadores, inseriu e redimensionou páginas, numerou, aplicou marca d'água, "
        "localizou texto e converteu para Word."
    )
    bundled = {path.name.split("-")[0].lower() for path in APP_DIR.glob("_internal/*.dist-info")}
    if missing := {"pymupdf", "pyhanko", "python_docx"} - bundled:
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
