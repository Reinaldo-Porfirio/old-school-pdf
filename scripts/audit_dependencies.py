"""Exporta metadados instalados, sem rede e sem dados de documentos."""

import argparse
import json
import platform
import sys
from importlib.metadata import distributions
from pathlib import Path

default_output = Path(__file__).resolve().parents[1] / "docs" / "evidence" / "dependencies.json"
parser = argparse.ArgumentParser(description="Inventariar as dependências instaladas")
parser.add_argument("--output", type=Path, default=default_output)
output = parser.parse_args().output
packages = []
for distribution in sorted(distributions(), key=lambda d: d.metadata["Name"].casefold()):
    metadata = distribution.metadata
    packages.append(
        {
            "name": metadata["Name"],
            "version": distribution.version,
            "requires_python": metadata.get("Requires-Python"),
            "license_expression": metadata.get("License-Expression"),
            "license": metadata.get("License"),
            "license_classifiers": [
                value for value in metadata.get_all("Classifier", []) if value.startswith("License")
            ],
            "project_urls": metadata.get_all("Project-URL", []),
            "license_files": [
                str(file)
                for file in (distribution.files or [])
                if any(term in str(file).lower() for term in ("license", "copying", "notice"))
            ],
        }
    )
output.parent.mkdir(parents=True, exist_ok=True)
output.write_text(
    json.dumps(
        {
            "platform": platform.platform(),
            "python": sys.version,
            "packages": packages,
        },
        ensure_ascii=False,
        indent=2,
    )
    + "\n",
    encoding="utf-8",
)
print(f"Inventário local: {len(packages)} distribuições em {output}")
