"""Verifica licença e inicialização do código contido no wheel, sem instalá-lo."""

import json
import sys
from importlib.metadata import version
from pathlib import Path
from tempfile import TemporaryDirectory
from zipfile import ZipFile

root = Path(__file__).resolve().parents[1]
release = version("old-school-pdf")
wheel = next((root / "dist").glob(f"old_school_pdf-{release}-*.whl"))
with ZipFile(wheel) as archive:
    names = archive.namelist()
    assert "oldschoolpdf/__main__.py" in names
    assert any(name.endswith("/licenses/LICENSE") for name in names)
    assert any(name.endswith("/licenses/THIRD_PARTY_NOTICES.md") for name in names)

sys.path.insert(0, str(wheel))
import oldschoolpdf  # noqa: E402
from oldschoolpdf.app import main  # noqa: E402

assert str(wheel) in oldschoolpdf.__file__, oldschoolpdf.__file__
with TemporaryDirectory(prefix="oldschoolpdf-wheel-") as scratch:
    settings = Path(scratch) / "wheel.ini"
    exit_code = main(["--smoke-test", "--settings-file", str(settings)])
    assert exit_code == 0
    assert settings.is_file()

print(
    json.dumps(
        {
            "wheel": wheel.name,
            "loaded_from_wheel": True,
            "license_files_present": True,
            "gui_start_and_close": "passed",
        },
        indent=2,
    )
)
