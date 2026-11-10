"""Entrada de `python -m oldschoolpdf` e do executável empacotado."""

import sys

from oldschoolpdf.infrastructure.pdf_worker import WORKER_FLAG


def run() -> int:
    if sys.argv[1:2] == [WORKER_FLAG]:
        from oldschoolpdf.infrastructure.pdf_worker import main as worker_main

        worker_main()
        return 0
    from oldschoolpdf.app import main

    return main()


if __name__ == "__main__":
    raise SystemExit(run())
