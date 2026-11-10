# Avisos de terceiros · DocForge 0.5.0

Atualizado em 10/11/2026. O código DocForge usa **AGPL-3.0-or-later**.
Cada componente conserva os termos dos respectivos titulares. O lock
registra as versões e os hashes resolvidos. O M5 mantém a base selecionada
no M1 e acrescenta o extra opcional de assinatura digital.

## Runtime

| Componente | Versão selecionada | Licença / origem |
|---|---|---|
| CPython (ambiente de desenvolvimento local) | 3.13.15 | PSF-2.0 e avisos incluídos na distribuição; https://docs.python.org/3/license.html |
| PySide6-Essentials / QtCore, QtGui, QtWidgets | 6.12.0 | LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only; opção LGPLv3 dos módulos usados; https://pypi.org/project/PySide6-Essentials/ |
| shiboken6 | 6.12.0 | LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only; https://pypi.org/project/shiboken6/ |
| PyMuPDF e MuPDF | 2.1 e 1.28.6 | Opção GNU AGPLv3 da licença dupla de Artifex. [Fontes](https://github.com/pymupdf/PyMuPDF) · [Termos](https://pymupdf.readthedocs.io/en/latest/about.html#license-and-copyright) |

PySide6, shiboken e Qt: © The Qt Company Ltd. e demais contribuidores, conforme
os avisos originais de cada pacote. Fontes e avisos oficiais:
https://code.qt.io/cgit/pyside/pyside-setup.git/ e
https://doc.qt.io/qtforpython-6/licenses.html.
Qt também contém componentes de terceiros com avisos específicos:
https://doc.qt.io/qt-6/licenses-used-in-qt.html.
Os pacotes instalados conservam seus arquivos LICENSES e metadados.

A versão 0.5.0 distribui o código do aplicativo. O inventário de uma distribuição
binária deve incluir os avisos dos módulos e plugins incluídos, as fontes
correspondentes conforme a licença, a possibilidade de substituir bibliotecas
LGPL e o inventário de codecs, fontes e componentes nativos.

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

Os caminhos de licenças e avisos dos wheels instalados constam no inventário
do M1. O aplicativo desativa o layout ONNX e usa o motor MuPDF padrão.
[Inventário](docs/evidence/m1-dependencies.json) · [ADR 0002](docs/decisions/0002-m1-viewer.md)

## Desenvolvimento

| Componente | Versão direta fixada | Licença |
|---|---|---|
| pytest | 9.2.0 | MIT — https://github.com/pytest-dev/pytest |
| pytest-qt | 4.5.0 | MIT — https://github.com/pytest-dev/pytest-qt |
| Ruff | 0.17.3 | MIT — https://github.com/astral-sh/ruff |
| Hatchling | 1.33.0 | MIT — https://github.com/pypa/hatch |
| build | 1.6.1 | MIT — https://github.com/pypa/build |

Inventário transitivo do ambiente resolvido (somente desenvolvimento):

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

O inventário completo de metadados e caminhos de avisos está em
`docs/evidence/m1-dependencies.json`, gerado sem rede pelo script
`scripts/audit_dependencies.py`. Esses pacotes não são necessários em runtime.
Não se modificou código de terceiros. As licenças permissivas e a MPL-2.0 dos
utilitários de desenvolvimento são compatíveis com este uso; preservar seus
avisos caso se redistribuam ferramentas junto com o projeto.
uv 0.12.5 é ferramenta externa de instalação (MIT OR Apache-2.0), não componente
embutido: https://github.com/astral-sh/uv.

Ações CI consultadas pela API oficial do GitHub e fixadas por commit em
04/11/2026: actions/checkout v7.0.1 (MIT), actions/setup-python v7.1.0 (MIT),
actions/upload-artifact v7.0.2 (MIT), astral-sh/setup-uv v10.3.3 (MIT).
São ferramentas do workflow, não componentes do aplicativo. Repositórios:
https://github.com/actions/checkout, https://github.com/actions/setup-python,
https://github.com/actions/upload-artifact, https://github.com/astral-sh/setup-uv.

## Assets

Ícones de comandos são desenhados por QPainter no próprio código
`src/docforge/ui/icons.py`, sob a licença do DocForge. Sem ícones copiados,
fontes baixadas, imagens externas ou assets proprietários. Controles nativos Qt
mantêm seus próprios avisos; a interface usa fontes já presentes no sistema.

## Dependências de marcos futuros

pikepdf, OCRmyPDF e LibreOffice não estão instalados
pelo projeto nem fixados. Suas licenças, módulos e dados serão verificados ao
introduzi-los, sem tomar a tabela da especificação como auditoria concluída.

## Extra opcional de assinatura digital do M5

**pyHanko 0.38.1**, MIT, Python 3.11 ou superior conforme metadados oficiais.
O extra `signing` é compatível com o intervalo de Python declarado pelo projeto.
A execução foi verificada no Python 3.13.15 x64 para Windows. O aplicativo
carrega o componente no processo PDF quando o usuário assina ou verifica uma
cópia. A validação local não busca certificados, revogação ou carimbos de tempo
em serviços externos. [PyPI oficial](https://pypi.org/project/pyHanko/0.38.1/) ·
[Código e licença](https://github.com/MatthiasValvekens/pyHanko)

| Dependência opcional resolvida | Versão | Termos nos metadados e avisos do wheel |
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
| lxml | 6.1.3 | BSD-3-Clause e avisos do wheel |
| multidict | 7.2.1 | Apache-2.0 |
| oscrypto | 1.3.0 | MIT |
| propcache | 0.5.4 | Apache-2.0 |
| pycparser | 3.12 | BSD-3-Clause |
| pyhanko-certvalidator | 0.33.0 | MIT |
| tzdata | 2026.6 | Apache-2.0 |
| tzlocal | 5.4.5 | MIT |
| uritools | 7.0.0 | MIT |
| yarl | 1.25.1 | Apache-2.0 |

O wheel do DocForge declara a dependência e preserva os avisos do próprio
projeto. O inventário registra também os caminhos dos avisos instalados.
Para a distribuição binária, revisar e preservar os avisos de todas as
bibliotecas nativas efetivamente incluídas. [Inventário M5](docs/evidence/m5-dependencies.json)

## OCR opt-in do M4

O PyMuPDF usa o Tesseract integrado ao MuPDF para OCR. Tesseract é distribuído
sob Apache-2.0. Os modelos `por.traineddata` e `eng.traineddata` usados na QA
vieram do release tessdata_fast 4.1.0 e conservam a licença Apache-2.0. Os
modelos de QA ficam na pasta ignorada pelo repositório. O pacote DocForge
consome modelos fornecidos pelo usuário. [Tesseract](https://github.com/tesseract-ocr/tesseract) ·
[Licença dos modelos](https://github.com/tesseract-ocr/tessdata_fast/blob/4.1.0/LICENSE)
