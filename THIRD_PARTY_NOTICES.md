# Avisos de terceiros · Old School PDF 0.6.1

Atualizado em 10/11/2026. O código do Old School PDF usa **AGPL-3.0-or-later**.
Cada componente de terceiros mantém os termos de quem o publicou. O `uv.lock`
registra as versões e os hashes resolvidos.

O projeto é distribuído de duas formas:

1. **Código-fonte**, neste repositório. As dependências são instaladas pelo `uv` ou pelo `pip`.
2. **Executável e instalador para Windows**, nas Releases do GitHub. Eles trazem
   dentro o Python e as bibliotecas listadas em
   [Distribuição binária](#distribuição-binária-executável-e-instalador).

## Runtime

| Componente | Versão | Licença / origem |
|---|---|---|
| CPython | 3.13.15 | PSF-2.0; https://docs.python.org/3/license.html |
| PySide6-Essentials / QtCore, QtGui, QtWidgets, QtSvg | 6.12.0 | LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only; usada a opção LGPLv3; https://pypi.org/project/PySide6-Essentials/ |
| shiboken6 | 6.12.0 | LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only; https://pypi.org/project/shiboken6/ |
| PyMuPDF e MuPDF | 2.1 e 1.28.6 | Opção GNU AGPLv3 da licença dupla da Artifex. [Fontes](https://github.com/pymupdf/PyMuPDF) · [Termos](https://pymupdf.readthedocs.io/en/latest/about.html#license-and-copyright) |

PySide6, shiboken e Qt: © The Qt Company Ltd. e demais contribuidores, conforme
os avisos originais de cada pacote. Fontes e avisos oficiais:
https://code.qt.io/cgit/pyside/pyside-setup.git/ e
https://doc.qt.io/qtforpython-6/licenses.html.
Qt também contém componentes de terceiros com avisos próprios:
https://doc.qt.io/qt-6/licenses-used-in-qt.html.

### Dependências do wheel PyMuPDF

| Componente | Versão | Termos identificados |
|---|---|---|
| pymupdf-layout e pymupdf4llm | 2.1 | Pacotes de metadados de compatibilidade. O código vem no PyMuPDF |
| ONNX Runtime | 1.31.1 | MIT e `ThirdPartyNotices.txt` do wheel |
| NumPy | 2.5.4 | BSD-3-Clause AND 0BSD AND MIT AND Zlib AND CC0-1.0, com avisos dos binários no wheel |
| NetworkX | 3.7 | BSD-3-Clause |
| PyYAML | 6.0.3 | MIT |
| psutil | 7.2.2 | BSD-3-Clause |
| tabulate | 0.10.0 | MIT |
| flatbuffers | 25.12.19 | Apache-2.0 |
| protobuf | 7.36.2 | BSD-3-Clause |
| packaging | 26.3 | Apache-2.0 OR BSD-2-Clause |

Esses pacotes são instalados junto com o PyMuPDF quando se roda a partir do
código-fonte. O aplicativo desliga o layout por ONNX e usa o motor padrão do MuPDF,
por isso **nenhum deles entra no executável**. Os caminhos de licenças e avisos dos
wheels instalados estão no inventário do M1.
[Inventário](docs/evidence/m1-dependencies.json) · [ADR 0002](docs/decisions/0002-m1-viewer.md)

## Extra de assinatura digital

**pyHanko 0.38.1**, MIT. No código-fonte é o extra opcional `signing`. No
executável já vem incluído. O componente só é carregado no processo PDF quando o
usuário assina ou verifica uma cópia. A validação local não busca certificados,
revogação ou carimbos de tempo em serviços externos.
[PyPI oficial](https://pypi.org/project/pyHanko/0.38.1/) ·
[Código e licença](https://github.com/MatthiasValvekens/pyHanko)

| Dependência resolvida | Versão | Termos nos metadados e avisos do wheel |
|---|---|---|
| aiohappyeyeballs | 2.7.1 | PSF-2.0 |
| aiohttp | 3.14.5 | Apache-2.0 AND MIT |
| aiosignal | 1.4.0 | Apache-2.0 |
| asn1crypto | 1.5.1 | MIT |
| attrs | 26.1.0 | MIT |
| certifi | 2026.10.23 | MPL-2.0 |
| cffi | 2.1.1 | MIT-0 |
| cryptography | 50.0.2 | Apache-2.0 OR BSD-3-Clause |
| frozenlist | 1.8.0 | Apache-2.0 |
| idna | 3.20 | BSD-3-Clause |
| lxml | 6.1.3 | BSD-3-Clause e avisos do wheel (libxml2, libxslt) |
| multidict | 7.2.1 | Apache-2.0 |
| oscrypto | 1.3.0 | MIT |
| propcache | 0.5.4 | Apache-2.0 |
| pycparser | 3.12 | BSD-3-Clause |
| pyhanko-certvalidator | 0.33.0 | MIT |
| tzdata | 2026.6 | Apache-2.0 |
| tzlocal | 5.4.5 | MIT |
| uritools | 7.0.0 | MIT |
| yarl | 1.25.1 | Apache-2.0 |

[Inventário M5](docs/evidence/m5-dependencies.json)

## OCR

O PyMuPDF usa o Tesseract integrado ao MuPDF para OCR. Tesseract é distribuído
sob Apache-2.0. **Os modelos de idioma não acompanham o projeto**: o usuário baixa
`por.traineddata` e `eng.traineddata`, por exemplo do release tessdata_fast 4.1.0,
sob Apache-2.0, e indica a pasta no aplicativo.
[Tesseract](https://github.com/tesseract-ocr/tesseract) ·
[Licença dos modelos](https://github.com/tesseract-ocr/tessdata_fast/blob/4.1.0/LICENSE)

## Distribuição binária (executável e instalador)

O executável `OldSchoolPDF.exe` e o instalador `OldSchoolPDF-<versão>-setup.exe`
são gerados por `packaging/build.py`. O executável contém:

- o runtime **CPython 3.13** (PSF-2.0). O texto da licença vai em `_internal/licenses/Python/LICENSE.txt`;
- **PySide6, shiboken6 e Qt 6.12** sob LGPL-3.0. As DLLs do Qt ficam como arquivos
  separados em `_internal/PySide6` e podem ser substituídas por versões compatíveis
  modificadas pelo usuário. Os textos da LGPL-3.0 e da GPL-3.0 vão em `_internal/licenses`;
- **PyMuPDF e MuPDF** sob AGPL-3.0. O código-fonte completo e correspondente do
  aplicativo é este repositório, na tag da versão (por exemplo, `v0.6.1`);
- **pyHanko** e as dependências da tabela acima, com os arquivos de licença de cada
  pacote em `_internal/*.dist-info`;
- **setuptools** 84.2.1 (MIT), incluído pelo PyInstaller como dependência de execução.

Ficam **fora** do executável: os modelos de layout ONNX do PyMuPDF e as dependências
listadas em "Dependências do wheel PyMuPDF", o OpenGL por software do Qt e as
traduções do Qt além do português do Brasil.

O executável é montado com **PyInstaller 6.22.3**, GPL-2.0-or-later com exceção
para o bootloader. A exceção permite distribuir o bootloader incluído no executável
sob qualquer licença ([termos](https://github.com/pyinstaller/pyinstaller/blob/develop/COPYING.txt)).
O instalador é criado com **Inno Setup 6**, cuja licença permite distribuir
instaladores gerados com ele, inclusive comercialmente
([termos](https://jrsoftware.org/files/is/license.txt)). Os textos das licenças
LGPL-3.0 e GPL-3.0 incluídos vêm da Free Software Foundation e estão em `packaging/licenses`.

## Desenvolvimento

| Componente | Versão direta fixada | Licença |
|---|---|---|
| pytest | 9.2.0 | MIT; https://github.com/pytest-dev/pytest |
| pytest-qt | 4.5.0 | MIT; https://github.com/pytest-dev/pytest-qt |
| Ruff | 0.17.3 | MIT; https://github.com/astral-sh/ruff |
| Hatchling | 1.33.0 | MIT; https://github.com/pypa/hatch |
| build | 1.6.1 | MIT; https://github.com/pypa/build |
| PyInstaller | 6.22.3 | GPL-2.0-or-later com exceção para o bootloader; https://github.com/pyinstaller/pyinstaller |

Inventário transitivo do ambiente de desenvolvimento:

| Componente | Versão | Licença conferida nos metadados/arquivos instalados |
|---|---|---|
| colorama | 0.4.6 | BSD-3-Clause |
| iniconfig | 2.3.1 | MIT |
| pathspec | 1.1.1 | MPL-2.0 |
| pluggy | 1.7.0 | MIT |
| Pygments | 2.21.0 | BSD-2-Clause |
| pyproject_hooks | 1.3.3 | MIT |
| tomlkit | 0.15.2 | MIT |
| trove-classifiers | 2026.9.21.13 | Apache-2.0 |
| typing_extensions | 4.16.0 | PSF-2.0 |
| pyinstaller-hooks-contrib | 2026.10 | GPL-2.0 OR Apache-2.0 |
| pywin32-ctypes | 0.2.3 | BSD-3-Clause |

O inventário de metadados e caminhos de avisos é gerado sem rede por
`scripts/audit_dependencies.py`. As ferramentas de desenvolvimento não fazem parte
do aplicativo distribuído. uv 0.12.5 é a ferramenta externa de instalação
(MIT OR Apache-2.0), não um componente embutido: https://github.com/astral-sh/uv.

As actions da CI estão fixadas por commit: actions/checkout v7.0.1, actions/setup-python
v7.1.0, actions/upload-artifact v7.0.2 e astral-sh/setup-uv v10.3.3, todas MIT. Elas
são ferramentas do workflow, não componentes do aplicativo.

## Assets

Os ícones dos comandos e o logotipo são SVG originais, escritos no próprio código
(`src/oldschoolpdf/ui/icon_art.py`) e licenciados como o resto do projeto. As
imagens do assistente de instalação são geradas a partir desse logotipo. Não há
ícones copiados, fontes baixadas, imagens externas ou assets proprietários. A
interface usa fontes já presentes no Windows, como Tahoma e Segoe UI. Os conceitos
visuais em `docs/concepts` usam apenas HTML/CSS e esses mesmos ícones.
