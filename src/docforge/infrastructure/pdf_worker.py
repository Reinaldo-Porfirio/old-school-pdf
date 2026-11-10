"""Processo de leitura de um PDF. O protocolo usa somente os pipes locais do pai."""

import json
import struct
import sys

from docforge.domain.errors import DocForgeError
from docforge.domain.viewer import MAX_REPLY_HEADER

FRAME = struct.Struct("!II")


def main() -> None:
    output = sys.stdout.buffer
    sys.stdout = sys.stderr

    from pymupdf import TOOLS

    from docforge.infrastructure.pdf_engine import PdfEngine
    from docforge.infrastructure.pdf_media import process_media
    from docforge.infrastructure.pdf_ocr import probe_ocr
    from docforge.infrastructure.pdf_storage import inspect_inputs, merge

    engine = PdfEngine()
    operations = {
        "open": engine.open,
        "password": engine.authenticate,
        "render": engine.render,
        "search": engine.search,
        "copy": engine.extract,
        "objects": engine.objects,
        "edit": engine.edit,
        "step": engine.step,
        "verify_signatures": engine.verify_signatures,
        "inspect_inputs": inspect_inputs,
        "merge": merge,
        "probe_ocr": probe_ocr,
    }

    def write_frame(header: dict, data: bytes = b"") -> None:
        encoded = json.dumps(header, allow_nan=False).encode("utf-8")
        if len(encoded) > MAX_REPLY_HEADER:
            encoded = b'{"error":"O resultado excede o limite do leitor."}'
            data = b""
        output.write(FRAME.pack(len(encoded), len(data)))
        output.write(encoded)
        output.write(data)
        output.flush()

    last_progress = -1

    def progress(done: int, total: int, detail: str) -> None:
        nonlocal last_progress
        value = min(99, 100 * done // total)
        if value > last_progress:
            last_progress = value
            write_frame({"progress": {"value": value, "detail": detail}})

    try:
        while line := sys.stdin.buffer.readline(4 * 1024 * 1024):
            data = b""
            request = None
            try:
                request = json.loads(line)
                if request["op"] in {"process_media", "export"}:
                    last_progress = -1
                    run = process_media if request["op"] == "process_media" else engine.export
                    result = run(**request["args"], progress=progress)
                else:
                    result = operations[request["op"]](**request["args"])
                if isinstance(result, tuple):
                    result, data = result
                header = {"result": result}
            except DocForgeError as error:
                header = {"error": str(error)}
            except OSError:
                header = {"error": "Não foi possível acessar o PDF ou a pasta de trabalho."}
            except Exception:
                header = {"error": "O leitor encontrou um problema ao processar este PDF."}
            finally:
                # Mensagens nativas podem conter trechos e caminhos fornecidos pelo PDF.
                TOOLS.mupdf_warnings(reset=True)
            write_frame(header, data)
            del request, line, data
    except BrokenPipeError:
        pass
    finally:
        engine.close()


if __name__ == "__main__":
    main()
