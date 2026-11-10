import sys

import oldschoolpdf.__main__ as entry
import oldschoolpdf.infrastructure.pdf_worker as pdf_worker
from oldschoolpdf.infrastructure.pdf_process import worker_command
from oldschoolpdf.infrastructure.pdf_worker import WORKER_FLAG


def test_source_checkout_runs_worker_module_in_isolated_mode(monkeypatch):
    monkeypatch.delattr(sys, "frozen", raising=False)
    program, arguments = worker_command()
    assert program == sys.executable
    assert arguments == ["-I", "-u", "-m", "oldschoolpdf.infrastructure.pdf_worker"]


def test_frozen_executable_starts_itself_as_worker(monkeypatch):
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", r"C:\Programas\Old School PDF\OldSchoolPDF.exe")
    assert worker_command() == (r"C:\Programas\Old School PDF\OldSchoolPDF.exe", [WORKER_FLAG])


def test_entry_point_dispatches_worker_flag(monkeypatch):
    calls = []
    monkeypatch.setattr(sys, "argv", ["OldSchoolPDF.exe", WORKER_FLAG])
    monkeypatch.setattr(pdf_worker, "main", lambda: calls.append("worker"))
    assert entry.run() == 0
    assert calls == ["worker"]
