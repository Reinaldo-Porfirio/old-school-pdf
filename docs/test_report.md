# Relatório de testes · DocForge Ultimate M5

**10/11/2026**, America/Sao_Paulo. DocForge 0.5.0. Windows 11 x64, build 22631.
CPython 3.13.15, PySide6-Essentials e Qt 6.12.0, PyMuPDF 2.1, MuPDF 1.28.6
e pyHanko opcional 0.38.1. A suíte incluiu os modelos locais de QA de OCR
de português e inglês, já disponíveis desde o M4.

## Execuções do M5

Comandos executados no PowerShell na raiz do projeto. Cada execução usou
uma pasta temporária e arquivos de teste sintéticos.

```powershell
$env:PYTHONUTF8 = '1'
$env:DOCFORGE_TEST_TESSDATA = Join-Path (Get-Location) '.cache/m4-qa/tessdata'
Remove-Item Env:QT_QPA_PLATFORM -ErrorAction SilentlyContinue
Remove-Item Env:QT_SCALE_FACTOR -ErrorAction SilentlyContinue
$m5Base = Join-Path (Get-Location) ('.cache/m5-windows-' + [guid]::NewGuid().ToString('N').Substring(0,8))
.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider --basetemp $m5Base --junitxml=docs/evidence/m5-pytest-windows.xml

$env:QT_QPA_PLATFORM = 'offscreen'
$m5Base = Join-Path (Get-Location) ('.cache/m5-headless-' + [guid]::NewGuid().ToString('N').Substring(0,8))
.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider --basetemp $m5Base --junitxml=docs/evidence/m5-pytest-headless.xml

Remove-Item Env:QT_QPA_PLATFORM -ErrorAction SilentlyContinue
$env:QT_SCALE_FACTOR = '1.5'
$m5Base = Join-Path (Get-Location) ('.cache/m5-dpi-' + [guid]::NewGuid().ToString('N').Substring(0,8))
.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider --basetemp $m5Base tests/gui/test_security.py --junitxml=docs/evidence/m5-pytest-dpi.xml
Remove-Item Env:QT_SCALE_FACTOR
```

| Verificação final | Resultado observado |
|---|---|
| Qt nativo no Windows | **109 aprovados**, 0 falhas, 0 ignorados. 97,24 s. [JUnit](evidence/m5-pytest-windows.xml) |
| Qt offscreen no Windows | **108 aprovados e 1 ignorado**, 0 falhas. 89,67 s. O caso de dock flutuante passou no nativo. [JUnit](evidence/m5-pytest-headless.xml) |
| Escala Qt 150% | **10 aprovados** em 13,87 s. Os demais 99 casos ficaram fora do filtro. [JUnit](evidence/m5-pytest-dpi.xml) |
| `ruff check .` e `ruff format --check .` | Passaram |
| `uv lock --check --offline` e `uv pip check --python .venv/Scripts/python.exe` | Passaram. 50 distribuições instaladas e compatíveis no ambiente de desenvolvimento |
| `python -m build --no-isolation` e `python scripts/verify_wheel.py` | Wheel verificado e inicialização da GUI com licenças presentes. [Smoke de distribuição](evidence/m5-smoke-wheel.json) |
| Instalação offline do wheel em ambiente isolado com `signing` | Importou da instalação, redigiu, reabriu, assinou e validou com raiz local no Qt nativo. [Smoke](evidence/m5-smoke-wheel-signing.json) |
| Instalação offline do wheel em ambiente isolado sem `signing` | Importou da instalação, redigiu e reabriu no Qt nativo. A assinatura digital ficou desabilitada. [Smoke](evidence/m5-smoke-wheel-base.json) |

Para os dois ambientes isolados, foram executados `uv sync --frozen --offline
--no-dev --no-install-project`, com `--extra signing` no ambiente de assinatura,
e `uv pip install --offline --no-deps --python <python-isolado> dist/docforge_ultimate-0.5.0-py3-none-any.whl`.
Os testes com janelas e as capturas usaram Qt Test, dados sintéticos e INI separado.

## Auditoria de segurança

- **Metadados.** A exportação removeu o título escolhido e o XMP, preservou
  autor, assunto, formulário e anexo, e dispensou revisão incremental.
  A limpeza da ficha inteira em um PDF criptografado preservou AES-256
  e as permissões após confirmar a senha do proprietário.
- **Criptografia.** A cópia reabriu com as duas senhas nos papéis esperados.
  A senha errada foi recusada. A opção de impressão incluiu alta qualidade.
  Permitir modificação de conteúdo não liberou organização de páginas no
  PDF AES-256. Também foram exercitados PDFs legados R2 com e sem permissão.
  Senhas de QA não apareceram no INI ou na fila.
- **T15.** A regressão conferiu o alerta de possível invalidação ao editar
  e exportar PDFs que indicam assinatura.
- **T16.** Uma cópia nova passou na extração de texto, auditoria da estrutura
  e inspeção de todos os pixels no interior das áreas marcadas. O teste
  usou texto visível e oculto, camada opcional oculta, imagem colorida,
  formulário, comentário, anexo, XMP, índice, link, ação de abertura e
  revisão incremental na entrada. Incluiu página recortada e girada e
  rotação do visualizador. A saída contém uma imagem RGB por página,
  com a cor de controle preservada fora da marca. A auditoria admite
  somente o identificador de produtor que o MuPDF cria para a saída.
  O cancelamento durante o progresso descartou o temporário e editar
  a revisão limpou as marcas.
- **T17.** Os caminhos por desenho e imagem informaram a ausência de
  verificação criptográfica. As duas aparências foram renderizadas após
  reabrir o PDF salvo. A marca visual ficou disponível no histórico.
- **Assinatura digital.** A senha incorreta do certificado foi recusada.
  O teste assinou com PKCS#12 sintético e confirmou a cobertura integral.
  A assinatura permaneceu íntegra sem uma raiz selecionada e a confiança
  foi estabelecida com a raiz de QA. A verificação distinguiu alteração de
  bytes e revisão incremental posterior. O teste bloqueou DNS e conexões
  externas no verificador e permitiu apenas loopback interno do asyncio no
  Windows. Nenhuma tentativa de conexão externa foi observada.
- **Preservação.** Os testes compararam os bytes das entradas antes e depois
  das exportações e verificaram o descarte de arquivos temporários.

O Poppler 26.07.0 reabriu de forma independente a saída de T16 com `pdfinfo`
e renderizou as duas páginas com `pdftoppm -r 150 -f 1 -l 2 -png`. O resultado
tinha 9.329 bytes e nenhuma ficha de formulário, metadado personalizado ou
JavaScript indicado. Os pixels `(300, 180)` e `(345, 195)` nas páginas 1 e 2
eram pretos. O controle verde `(0, 191, 0)` permaneceu na página 1.
O `pdfinfo` informou tamanho zero ao receber o caminho Unicode neste
ambiente. Uma cópia de QA em caminho ASCII retornou o tamanho correto.

[Prévia da redação no Classic Light](evidence/m5-redacao-previa.png) ·
[Relatório de assinatura no Graphite Pro](evidence/m5-assinatura-digital.png) ·
[Inventário das dependências instaladas](evidence/m5-dependencies.json) ·
[Decisões e protótipo de texto existente](decisions/0005-m5-security.md)

## Falhas encontradas e limites

- A resolução inicial de `uv lock --offline` falhou porque o cache não
  tinha todos os metadados transitivos. A atualização do lock e instalação
  do extra via PyPI passaram em uma chamada autorizada. A resolução
  subsequente e a instalação dos wheels de QA passaram offline.
- Um protótipo de assinatura recusou um PDF sintético com XMP malformado.
  A interface passou a explicar a incompatibilidade desse XMP. Os testes
  de assinatura usaram PDFs com XMP válido ou ausente.
- As primeiras rodadas focadas em `tests/gui/test_security.py` tiveram
  6 aprovados e 2 falhas de consulta à API da fila. Após o ajuste, a rodada
  seguinte teve 7 aprovados e 1 falha por causa do campo de produtor
  gerado pelo MuPDF. A auditoria passou a reconhecer apenas esse valor
  esperado. As rodadas seguintes passaram com 8 casos e, após adicionar
  as verificações R2, com 10 casos.
- A primeira suíte M5 no Qt nativo teve 106 aprovados. No offscreen, foram
  103 aprovados, 2 falhas e 1 ignorado. O relatório de assinatura gerou o
  aviso de geometria esperado do plugin, tratado apenas nesse teste.
  Um cancelamento em conversão deixou um PNG temporário bloqueado.
  Foram acrescentadas novas tentativas de limpeza no Windows e um teste de
  bloqueio transitório. A rodada offscreen seguinte teve 106 aprovados
  e 1 ignorado antes dos dois casos legados R2.
- O protótipo de edição de texto existente encontrou três trechos e
  posições por caractere, com uma fonte em subconjunto. A frase maior
  excedeu a caixa disponível em 141,78 pt. A edição permanece em pesquisa.
- Não foram executados testes em Windows 10, Linux, Python 3.12 ou 3.14,
  com certificados reais, leitores de tela ou múltiplos monitores.
  Instalador, atualização e desinstalação pertencem ao M6.

## Checklist do M5

- [x] Remover metadados selecionados e reabrir a cópia.
- [x] Reabrir a cópia AES-256 e conferir as permissões.
- [x] Revisar marcas e auditar a redação por texto, pixels e estrutura.
- [x] Inserir e reabrir assinatura visual com aviso.
- [x] Assinar e verificar offline com o extra opcional.
- [x] Registrar o piloto de edição de texto existente e seus limites.

`.\.venv\Scripts\python.exe -m docforge` abre o aplicativo no Windows.

---

# Relatório de testes · DocForge Ultimate M4

**10/11/2026**, America/Sao_Paulo. DocForge 0.4.0. Windows 11 x64, build 22631.
CPython 3.13.15, Qt 6.12.0, PyMuPDF 2.1 e MuPDF 1.28.6.

## Execuções finais

Comandos no PowerShell na raiz do projeto. Cada execução usa uma pasta temporária
distinta. O fator de escala do Qt foi usado na rodada a 150%.

```powershell
$env:DOCFORGE_TEST_TESSDATA = Join-Path (Get-Location) '.cache/m4-qa/tessdata'
Remove-Item Env:QT_QPA_PLATFORM -ErrorAction SilentlyContinue
$m4Base = Join-Path (Get-Location) ('.cache/m4-windows-' + [guid]::NewGuid().ToString('N').Substring(0,8))
.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider --basetemp $m4Base --junitxml=docs/evidence/m4-pytest-windows.xml

$env:QT_QPA_PLATFORM = 'offscreen'
$m4Base = Join-Path (Get-Location) ('.cache/m4-headless-' + [guid]::NewGuid().ToString('N').Substring(0,8))
.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider --basetemp $m4Base --junitxml=docs/evidence/m4-pytest-headless.xml

Remove-Item Env:QT_QPA_PLATFORM -ErrorAction SilentlyContinue
$env:QT_SCALE_FACTOR = '1.5'
$m4Base = Join-Path (Get-Location) ('.cache/m4-dpi-' + [guid]::NewGuid().ToString('N').Substring(0,8))
.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider --basetemp $m4Base -k 't13 or t18' --junitxml=docs/evidence/m4-pytest-dpi.xml
```

| Execução | Resultado observado |
|---|---|
| Qt nativo no Windows | **102 aprovados**, 0 falhas, 0 ignorados. 90,40 s. [JUnit](evidence/m4-pytest-windows.xml) |
| Qt offscreen no Windows | **101 aprovados e 1 ignorado**, 0 falhas. 82,60 s. O caso de dock flutuante passou no nativo. [JUnit](evidence/m4-pytest-headless.xml) |
| Escala Qt 150% | **3 aprovados** em 12,21 s. Os outros 99 casos ficaram fora do filtro. [JUnit](evidence/m4-pytest-dpi.xml) |
| `ruff check .` e `ruff format --check .` | Aprovados. 71 arquivos formatados |
| `uv lock --offline`, `uv lock --check --offline`, `uv sync --frozen --offline` e `uv pip check --python .venv/Scripts/python.exe` | Lock da versão 0.4.0 consistente, instalação offline aprovada e 29 distribuições compatíveis |
| `python -m build --no-isolation` e `python scripts/verify_wheel.py` | Fonte e wheel 0.4.0 gerados. Inicialização, encerramento e arquivos de licença do wheel conferidos |
| `uv sync --frozen --offline --no-dev --no-install-project` e `uv pip install --offline --no-deps` | 14 dependências e wheel em ambiente isolado. Configuração dos idiomas, OCR, reabertura e busca passaram no Qt nativo. [Smoke do wheel](evidence/m4-smoke-wheel.json) |

## Aceitação

| Caso | Resultado observado |
|---|---|
| T13 | O processo validou modelos de português e inglês e criou uma camada pesquisável em uma digitalização girada em cada idioma. A busca no DocForge encontrou as frases. A página com texto e a página fora do intervalo foram preservadas |
| T14 | Sem modelos validados, Reconhecer texto ficou indisponível e Configurar OCR local exibiu o caminho de configuração. O teste de modelo incompatível também manteve o OCR desativado |
| T18 | Dez abas permaneceram abertas. Durante o progresso do lote, o teste alternou de aba e verificou a ação de busca. Uma entrada corrompida falhou entre duas entradas concluídas e a repetição retomou apenas a falha |

Casos adicionais verificaram cancelamento durante a conversão, preservação de
uma pasta preexistente, PNG/JPEG, TIFF multipágina na ordem e tamanho escolhidos,
extração TXT UTF-8 e imagens compartilhadas, divisão e mesclagem em lote,
compactação estrutural com renderização idêntica e recompressão com redução de
dimensões. Uma operação de otimização com indicação de assinatura e sem ciência
explícita foi bloqueada. Os testes compararam os bytes das entradas.

## Verificação visual e interoperabilidade

Na janela nativa do Windows, a amostra `Amostra OCR M4.pdf` foi aberta com um
INI de teste separado. Pelo controle da janela, o fluxo selecionou a pasta,
enviou duas páginas em português a 200 DPI para a fila, abriu a cópia pelo
relatório e buscou `revisão técnica`. A janela mostrou `1/2 · Busca concluída`
e realçou o trecho correto. Ctrl+Q encerrou o aplicativo com código 0.

O smoke automatizado no Qt nativo capturou o diálogo, o relatório com detalhes
e a busca em Graphite Pro. Os dois idiomas foram testados pelo diálogo de
configuração e a amostra processada ficou com dois resultados de busca. As
duas páginas renderizaram com pixels idênticos a 100 DPI no PyMuPDF. O smoke
conferiu o hash da origem e registrou zero avisos Qt.
[Opções de OCR](evidence/m4-ocr-opcoes.png) · [Relatório](evidence/m4-relatorio.png) ·
[Busca em Graphite Pro](evidence/m4-ocr-busca.png) · [Smoke nativo](evidence/m4-smoke-native.json)

O `pdfinfo` do Poppler reconheceu o PDF final com duas páginas. O comando
`pdftoppm -r 90 -f 1 -l 1 -singlefile -png` gerou o mesmo PNG para a primeira
página original e a página com OCR. SHA-256 do PNG
`2b8bf44ab197f4a07d099f72f56eca6046eba0f51c58c5c44450bf1085db6076`.

## Dependências de teste

Os modelos foram obtidos do release tessdata_fast 4.1.0 para a QA local e
ficam em `.cache/m4-qa/tessdata`. O pacote do aplicativo usa os modelos
apontados pelo usuário. [Release dos modelos](https://github.com/tesseract-ocr/tessdata_fast/releases/tag/4.1.0)

| Arquivo | SHA-256 observado |
|---|---|
| `por.traineddata` | `c4932b937207a9514b7514d518b931a99938c02a28a5a5a553f8599ed58b7deb` |
| `eng.traineddata` | `7d4322bd2a7749724879683fc3912cb542f19906c83bcc1a52132556427170b2` |
| `LICENSE` | `cfc7749b96f63bd31c3c42b5c471bf756814053e847c10f3eb003417bc523d30` |

## Ocorrências e limites da validação

- A primeira execução do smoke encontrou uma importação incorreta de `abspath`
  no diálogo de configuração. O smoke de inicialização passou depois do ajuste.
- A primeira rodada dirigida teve sete aprovados e duas falhas em T13. O PDF
  já continha o texto e a busca nativa do motor o encontrou. A busca do DocForge
  perdeu a sequência de palavras em páginas giradas. Os dois casos passaram
  após preservar a ordem dos termos extraídos nessas páginas.
- A primeira regressão completa teve 101 aprovados e uma falha no Windows nativo.
  O modo offscreen teve 100 aprovados, uma falha e um ignorado. O otimizador
  recomprimiu a imagem sem alterar as dimensões daquela amostra. Ensaios
  confirmaram a redução em etapas de 2×. A opção passou a descrever o alvo como
  referência e o teste final inclui uma amostra efetivamente reduzida.
- LibreOffice e OCRmyPDF externos ficaram fora da validação neste Windows.
  A conversão via LibreOffice permanece indisponível. A validação observada
  cobre Windows 11 e Python 3.13. Windows 10, Linux, Python 3.12/3.14, CI remota,
  leitor de tela e múltiplos monitores ficaram fora do ambiente de teste.

Detalhes do motor, limites e publicação em novas pastas. [ADR 0004](decisions/0004-m4-media.md)

---

# Histórico de testes · DocForge Ultimate M2 e M3

**09/11/2026**, America/Sao_Paulo. DocForge 0.3.0. Windows 11 x64, build 22631.
CPython 3.13.15, Qt 6.12.0, PyMuPDF 2.1 e MuPDF 1.28.6.

## Execuções finais

Os testes foram executados no PowerShell a partir da raiz. Cada execução usou
um diretório temporário distinto em `.cache`.

```powershell
Remove-Item Env:QT_QPA_PLATFORM -ErrorAction SilentlyContinue
$m23Base = Join-Path (Get-Location) ('.cache/m23-windows-' + [guid]::NewGuid().ToString('N').Substring(0,8))
.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider --basetemp $m23Base --junitxml=docs/evidence/m23-pytest-windows.xml

$env:QT_QPA_PLATFORM = 'offscreen'
$m23Base = Join-Path (Get-Location) ('.cache/m23-headless-' + [guid]::NewGuid().ToString('N').Substring(0,8))
.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider --basetemp $m23Base --junitxml=docs/evidence/m23-pytest-headless.xml

Remove-Item Env:QT_QPA_PLATFORM -ErrorAction SilentlyContinue
$env:QT_SCALE_FACTOR = '1.5'
$m23Base = Join-Path (Get-Location) ('.cache/m23-dpi-' + [guid]::NewGuid().ToString('N').Substring(0,8))
.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider --basetemp $m23Base -k 't04 or t05 or t08 or t12 or continuous' --junitxml=docs/evidence/m23-pytest-dpi.xml
```

| Execução | Resultado observado |
|---|---|
| Qt nativo no Windows | **96 aprovados**, 0 falhas, 0 ignorados. 81,97 s. [JUnit](evidence/m23-pytest-windows.xml) |
| Qt offscreen no Windows | **95 aprovados e 1 ignorado**, 0 falhas. 72,21 s. O caso de dock flutuante passou no nativo. [JUnit](evidence/m23-pytest-headless.xml) |
| Escala Qt 150% | **5 aprovados** em 9,79 s. Os outros 91 casos ficaram fora do filtro. [JUnit](evidence/m23-pytest-dpi.xml) |
| `ruff check .` e `ruff format --check .` | Aprovados. 60 arquivos formatados |
| `uv lock --offline`, `uv sync --frozen --offline` e `uv pip check --python .venv/Scripts/python.exe` | Lock atualizado para 0.3.0, instalação offline aprovada e 29 distribuições compatíveis |
| `python -m build --no-isolation` e `python scripts/verify_wheel.py` | Fonte e wheel 0.3.0 gerados. Abertura, encerramento e arquivos de licença do wheel verificados |
| `uv sync --frozen --offline --no-dev --no-install-project` e `uv pip install --offline --no-deps` | 14 dependências e o wheel em ambiente isolado. Leitura, reordenação, anotações, preenchimento, exportação, reabertura e rolagem passaram no plugin Windows. [Smoke do wheel](evidence/m23-smoke-wheel.json) |

## Aceitação e proteção de arquivos

| Caso | Resultado |
|---|---|
| T06 | O diálogo conferiu as entradas de 3 e 5 páginas. A saída reabriu com 8 páginas na ordem escolhida e campos da segunda entrada |
| T07 | `2–4` gerou três páginas. O teste conferiu múltiplas partes, extração na ordem digitada e apenas os campos das páginas retidas |
| T08 | O modelo de miniaturas recebeu o payload de arraste. Reordenação, rotação persistente, exclusão, desfazer e refazer foram verificados após reabrir |
| T09 | A fila cancelou uma exportação em execução. A saída e os temporários foram descartados. A revisão ficou disponível e a nova tentativa gravou |
| T10 | Pasta inexistente, permissão negada simulada e destino bloqueado por um handle do Windows preservaram os originais e a edição |
| T11 | Cancelar manteve a aba. Descartar fechou. Salvar gerou uma cópia válida antes de fechar |
| T12 | Os gestos Qt inseriram oito tipos de anotação. O teste reposicionou e editou um comentário em página girada, desfez e refez a exclusão de um objeto e reabriu a saída |
| T15 | O aplicativo alertou antes de editar ou exportar um PDF com `SigFlags` e uma amostra com assinatura CMS destacada. O cancelamento preservou a revisão e os bytes de origem |
| T22 | O arquivo de origem e seu vínculo físico foram protegidos. O destino existente exigiu confirmação e a substituição preservou uma cópia de segurança byte a byte |

A suíte também verificou valores AcroForm de texto, checkbox e escolha,
desfazer/refazer, bloqueio de campo com script, recuperação após encerramento
do processo, rolagem virtualizada e manutenção de senha, AES de 256 bits e
permissões ao editar um PDF protegido. A regressão M0 e M1 rodou nas duas suítes.

A amostra sintética `tests/fixtures/assinado-t15.pdf` usa certificado local
autossinado e CMS destacado. Os bytes indicados pelo `ByteRange` foram verificados
com `System.Security.Cryptography.Pkcs.SignedCms.CheckSignature($true)` no Windows.
A checagem independente confirma a assinatura da amostra. O aplicativo exibe
somente a indicação de assinatura e o alerta de possível invalidação.
SHA-256 da amostra `1799aafe2a1614556addb34b2026d799b8e7d48dafe1e77575e9633d09971c49`.

## Verificação visual e interoperabilidade

As capturas foram feitas por uma verificação automatizada de widgets no Qt
nativo. O fluxo reordenou quatro páginas, inseriu três anotações, preencheu um
campo, exportou e conferiu o PDF. Os dois temas renderizaram sem avisos Qt e
o SHA-256 da origem permaneceu igual. A edição e a rolagem contínua aparecem
nas capturas. [Classic Light](evidence/m23-classic-light.png) ·
[Graphite Pro](evidence/m23-graphite-pro.png) · [Smoke nativo](evidence/m23-smoke-native.json)

O `pdfinfo` do Poppler 26.07.0 reconheceu `Form: AcroForm` na saída reordenada
de quatro páginas e na divisão de três páginas. A execução de
`pdftoppm -r 90 -f 1 -l 1 -singlefile -png` retornou 0 e gerou a primeira página
com destaque, caixa de texto, carimbo e campo preenchido. O Poppler emitiu avisos
de fonte para Symbol e ArialUnicode. Os elementos renderizados estavam legíveis.

## Ocorrências e limites da validação

- A primeira rodada de mesclagem falhou na prévia com `OverflowError` na
  conversão de identificadores de arquivo para Qt. Os metadados passaram a ser
  mantidos em Python e a rodada seguinte passou.
- As rodadas de anotações encontraram falhas na caixa de texto sem formatação,
  no reconhecimento de PNG e no ponto de comentários em páginas giradas.
  Os três ajustes passaram no T12 e na rodada a 150%.
- Uma rodada focada passou 14 casos e falhou na verificação de recuperação. A
  aba ainda tinha o raster antigo enquanto reabria. A tela agora limpa a imagem
  e o teste aguarda a revisão pronta.
- A primeira suíte completa com o teste de criptografia falhou na comparação
  literal do rótulo `AES-256`. O motor reporta `Standard V5 R6 256-bit AES`.
  A versão final verifica a autenticação e compara a proteção com a origem.
- O Poppler encontrou ausência do registro AcroForm numa saída que o PyMuPDF
  ainda reconhecia por seus widgets. Reordenação, divisão e extração passaram
  a preservar os campos compatíveis. Os testes agora conferem o registro.
- O smoke foi automatizado em uma estação Windows 11. Windows 10, Linux,
  Python 3.12 e 3.14, CI remota, leitor de tela e múltiplos monitores ficaram
  fora das execuções observadas. O teste de escala usa o fator de escala do Qt.

As regras de segurança e os limites de compatibilidade estão na decisão do
marco. [ADR 0003](decisions/0003-m2-m3-editing.md)

---

# Histórico de testes · DocForge Ultimate M1

**09/11/2026**, America/Sao_Paulo. DocForge 0.2.0. Windows 11 x64, build 22631.
CPython 3.13.15, Qt 6.12.0, PyMuPDF 2.1 e MuPDF 1.28.6.

## Execuções

Use a pasta do projeto no PowerShell. O caminho temporário de cada execução
foi único e ficou em `.cache`.

```powershell
$m1TestTemp = Join-Path 'D:\Projetos\DOC\.cache' ('m1-test-' + [guid]::NewGuid().ToString('N'))
Remove-Item Env:QT_QPA_PLATFORM -ErrorAction SilentlyContinue
.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider --basetemp $m1TestTemp --junitxml=docs/evidence/m1-pytest-windows.xml

$m1TestTemp = Join-Path 'D:\Projetos\DOC\.cache' ('m1-headless-' + [guid]::NewGuid().ToString('N'))
$env:QT_QPA_PLATFORM = 'offscreen'
.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider --basetemp $m1TestTemp --junitxml=docs/evidence/m1-pytest-headless.xml
```

| Execução | Resultado |
|---|---|
| Windows nativo | **92 aprovados** em 79,34 s, com saída 0. [JUnit](evidence/m1-pytest-windows.xml) |
| Headless | **91 aprovados e 1 ignorado** em 66,34 s, com saída 0. O teste de painel flutuante passou no nativo. [JUnit](evidence/m1-pytest-headless.xml) |
| Zoom e busca com `QT_SCALE_FACTOR=1.5` | **2 aprovados** com `-k 't04 or t05'` em 2,36 s. [JUnit](evidence/m1-pytest-dpi.xml) |
| `python -m ruff check .` e `python -m ruff format --check .` | Ambos aprovados |
| `uv pip check --python .venv/Scripts/python.exe` | 29 distribuições compatíveis |
| `python -m build --no-isolation` e `python scripts/verify_wheel.py` | Fonte e wheel 0.2.0 gerados. Licenças e inicialização pelo wheel verificadas |
| Instalação local do wheel em ambiente separado | 14 dependências resolvidas offline pelo lock e wheel instalado. Leitura, miniaturas, busca e encerramento passaram no plugin Windows |

Os cinco casos prioritários passaram no modo nativo e no headless.

| ID | Evidência de aceitação |
|---|---|
| T01 | Arquivo com nome Unicode abriu via ação de menu. Página 1, total e miniaturas apareceram. Clique, campo de página e abas funcionaram |
| T02 | PDF AES-256 pediu senha. Senha incorreta permitiu nova tentativa. A correta abriu a página e a restrição de cópia foi respeitada |
| T03 | Arquivos com cabeçalho inválido e estrutura corrompida receberam mensagens distintas. O PDF saudável continuou navegável |
| T04 | Zoom 50% e 200% manteve a proporção. Ajustes e rotação visual funcionaram e os bytes do PDF foram preservados |
| T05 | Busca em maiúsculas com acentos encontrou duas ocorrências. F3 avançou à página 3. A cópia retornou só o trecho selecionado |

A suíte também verificou cancelamento de abertura e busca, prazo excedido,
320 páginas com miniaturas sob demanda, rejeição de URLs remotas, migração
das preferências e regressões de interface e persistência do M0.

## Conferência visual e interação

Uma amostra sintética de três páginas foi criada com ReportLab 4.4.9 e
renderizada no Poppler com `pdftoppm -r 85 -f 1 -l 1 -singlefile -png`.
A página de referência saiu com código 0 e avisos de fontes de substituição
Symbol e ArialUnicode. O conteúdo da amostra ficou legível e a comparação
visual confirmou as proporções, os textos, a tabela e o rodapé.

Na sessão nativa, `python -m docforge --settings-file <INI de teste> <PDF>`
abriu a amostra. O controle de janela exerceu Ctrl+F, preencheu a consulta,
acionou a busca, navegou com F3, girou a página e selecionou a segunda
miniatura. Ctrl+Q fechou a sessão com código 0. O SHA-256 do PDF antes e
depois foi `701b9e2875ed4acf08d640a8803d393d5e605d9ad6197827f15bb5f4804d9370`.

A conferência encontrou a seleção anterior ainda pintada no painel de
miniaturas. A atualização passou a substituir a seleção e a notificar a
lista. O teste T05 verifica a seleção única. As capturas após a correção
mostram a página separada do fundo e a ocorrência ativa alinhada ao texto.
[Classic Light](evidence/m1-classic-light.png) ·
[Graphite Pro](evidence/m1-graphite-pro.png) · [Smoke nativo](evidence/m1-smoke.json)

O smoke via Qt confirmou a leitura em ambos os temas, três miniaturas, busca,
troca de ocorrência e preservação do arquivo. O registro de avisos e erros Qt
ficou vazio. O mesmo fluxo foi repetido a partir do wheel instalado em ambiente
separado com `uv sync --frozen --offline --no-dev --no-install-project` e
`uv pip install --offline --no-deps`.

## Ocorrências da execução

- A primeira tentativa de pytest foi interrompida por acesso negado ao cache
  legado. Com `-p no:cacheprovider` e diretório temporário novo, os 12 testes
  dirigidos passaram. As execuções finais usaram a mesma configuração.
- Ruff apontou inicialmente uma linha longa, um argumento padrão construído em
  chamada e uma variável de laço capturada no teste. Os ajustes passaram nas
  verificações finais.
- A primeira instalação isolada com requisitos exportados falhou na resolução
  offline. A instalação por `uv sync --frozen --offline` usou os artefatos do
  lock e permitiu validar o wheel com a rede desabilitada.
- Windows 10, Linux, CI remota, leitor de tela e múltiplos monitores ficam fora
  dos resultados observados. Os testes T06–T18 e T20–T22 correspondem a marcos
  posteriores. T19 cobre preferências e layout.

Licenças, versões e limites do leitor estão na decisão técnica do M1.
[ADR 0002](decisions/0002-m1-viewer.md) · [Inventário](evidence/m1-dependencies.json)

---

# Histórico de testes · DocForge Ultimate M0

Data: **04/11/2026**, America/Sao_Paulo. Escopo: **somente M0**.

## Resultado

**88 testes aprovados no Windows nativo, sem falhas, erros ou testes ignorados.**
Em headless: **87 aprovados e 1 ignorado**, sem falhas ou erros. O teste ignorado
de painel flutuante passou na execução nativa. Análise estática, formatação,
inicialização em processo separado e build também passaram.

O alicerce técnico está implementado e demonstrável. A inspeção visual de capturas
foi realizada. A avaliação interativa com mouse/teclado pelo helper de controle
de janela não pôde ser executada; o aceite humano completo continua pendente.
Não se afirma que PDFs, OCR, exportação ou instalador foram testados ou entregues.

## Ambiente efetivamente usado

| Item | Observado |
|---|---|
| Sistema | Windows 11 x64, NT 10.0.22631; `platform.platform()`: `Windows-11-10.0.22631-SP0` |
| Shell | PowerShell |
| Python | CPython 3.13.15, MSC v.1944, AMD64 |
| Ambiente | `.venv`, interpretador isolado em `.tools/python` |
| Instalador de pacotes | uv 0.12.5; cache do projeto `.cache/uv` |
| Interface | PySide6-Essentials / Qt 6.12.0, shiboken6 6.12.0 |
| Testes | pytest 9.2.0, pytest-qt 4.5.0, pluggy 1.7.0 |
| Qualidade e build | Ruff 0.17.3, Hatchling 1.33.0, build 1.6.1 |
| Plugins Qt usados | `windows` (nativo) e `offscreen` (headless) |

A pasta de trabalho estava vazia; Git foi inicializado sem substituir trabalho.
A especificação original foi copiada integralmente para `docs/product_spec.md`.
SHA-256 idêntico nas duas cópias:
`376A8BB845581A49CB4929AA585ECFC5EB05324348B57938741EA86ED90F4846`.
Não se alterou o arquivo de Downloads.

## Comandos e resultados reais

Comandos executados em `D:\Projetos\DOC`. Em PowerShell, foi usado
`$env:PYTHONUTF8 = '1'` para saída UTF-8. Os comandos abaixo usam diretamente o
ambiente isolado, pois o `python` global não estava disponível inicialmente.

| Comando | Resultado observado |
|---|---|
| `python --version` / `py -0p` na inspeção inicial | Python não encontrado / nenhum interpretador visível ao launcher |
| `uv python install 3.13 --no-bin` | Primeira tentativa com rede restrita falhou (10013); tentativa autorizada instalou 3.13.15 localmente |
| `uv sync --python .tools/python/cpython-3.13.15-windows-x86_64-none/python.exe` | 18 distribuições instaladas; lock gerado com hashes |
| `uv sync --frozen --offline` | Passou: `Checked 18 packages in 2ms`, sem download |
| `uv run --no-sync python -m docforge --version` | Passou: `0.1.0` |
| `.\.venv\Scripts\python.exe -m ruff check .` | Passou: `All checks passed!` |
| `.\.venv\Scripts\python.exe -m ruff format --check .` | Passou: `42 files already formatted` na verificação final |
| `.\.venv\Scripts\python.exe -m compileall -q src` | Passou, sem mensagens de erro |
| `.\.venv\Scripts\python.exe -m pytest tests/integration/test_settings.py -q` | Passou: **15 aprovados**, incluindo falha física de escrita e preservação de arquivos não pertencentes ao app |
| `.\.venv\Scripts\python.exe -m pytest -q --junitxml=docs/evidence/pytest-windows.xml` | Plugin nativo: **88 aprovados em 89,88 s**, código de saída 0 |
| `.\.venv\Scripts\python.exe -m pytest -q --junitxml=docs/evidence/pytest-headless.xml` | Headless: **87 aprovados, 1 ignorado em 70,63 s**, código de saída 0 |
| `.\.venv\Scripts\python.exe scripts/smoke_app.py` | Plugin `windows`: round-trip completo, nenhuma falha e nenhum aviso/erro Qt |
| `.\.venv\Scripts\python.exe scripts/audit_dependencies.py` | Inventário de 18 distribuições gerado sem rede |
| `.\.venv\Scripts\python.exe -m build --no-isolation` | Passou: sdist e wheel gerados, sem instalador |
| `.\.venv\Scripts\python.exe scripts/verify_wheel.py` | Código carregado do próprio wheel; licenças presentes; janela abriu, gravou INI de teste e encerrou, saída 0 |

Para o teste nativo, a variável `QT_QPA_PLATFORM` foi removida:

```powershell
Remove-Item Env:QT_QPA_PLATFORM -ErrorAction SilentlyContinue
.\.venv\Scripts\python.exe -m pytest -q --junitxml=docs/evidence/pytest-windows.xml
```

Para o headless:

```powershell
$env:QT_QPA_PLATFORM = 'offscreen'
.\.venv\Scripts\python.exe -m pytest -q --junitxml=docs/evidence/pytest-headless.xml
```

No Windows, `tests/conftest.py` indica as fontes já instaladas em `%WINDIR%\Fonts`
ao plugin offscreen por `QT_QPA_FONTDIR`; não baixa nem distribui fontes.
Avisos Qt de nível WARNING ou superior continuam configurados como falhas.
Para a conferência offline com uv, foram usados `UV_CACHE_DIR=.cache/uv` e
`UV_PYTHON_INSTALL_DIR=.tools/python`, expandidos para caminhos absolutos do projeto.

## Quais testes passaram

Todos os casos nomeados em [pytest-windows.xml](evidence/pytest-windows.xml)
passaram. O XML contém cada ID, inclusive os 32 comandos futuros parametrizados.

| Arquivo | Casos aprovados no modo nativo | Evidência funcional |
|---|---:|---|
| `tests/gui/test_dialogs.py` | 5 | Aceitar/cancelar preferências, conflitos de atalhos, erro de escrita, cancelar saída e descarte explícito das preferências |
| `tests/gui/test_window.py` | 41 | Widgets/menus pt-BR, comandos futuros desabilitados, abas, atalhos com barras ocultas, temas, geometria, organização/visibilidade, ícones e painel flutuante |
| `tests/integration/test_boundaries.py` | 4 | Fronteiras de importação, diagnóstico/inicialização sem rede/processos externos, rejeição de arrastar arquivos, entrypoint real e console vazio |
| `tests/integration/test_settings.py` | 15 | Round-trip binário e Unicode, padrões, configuração inválida, atalhos inválidos/duplicados, versão desconhecida, falha de escrita e proteção de arquivos alheios |
| `tests/unit/test_capabilities.py` | 3 | Dependências ausentes/presentes, recursos futuros nunca habilitados e probe local sem executar binários |
| `tests/unit/test_jobs.py` | 10 | Ciclo de vida, snapshots imutáveis, transições, cancelamento cooperativo, resultado parcial não publicado, concorrência e falhas |
| `tests/unit/test_models.py` | 10 | Estado independente por sessão, zoom, rotação, cópia distinta da origem e ausência de leitura/escrita documental |
| **Total** | **88** | **0 falhas / 0 erros / 0 ignorados no nativo** |

O único caso ignorado no headless foi
`test_native_floating_dock_restores_without_losing_it`: o plugin offscreen não
suporta integralmente janelas flutuantes. Esse mesmo caso passou no plugin
`windows`. Lista completa da rodada: [pytest-headless.xml](evidence/pytest-headless.xml).

O teste de entrypoint executa efetivamente:
`python -m docforge --settings-file <INI temporário com Unicode> --smoke-test`.
Ele verifica saída 0, stdout/stderr vazios e layout gravado. A opção de diagnóstico
fecha a janela após 300 ms; a execução normal não possui esse encerramento.

## Falhas encontradas e corrigidas

A primeira rodada, antes das correções, teve **77 aprovados e 4 falhas**, em
62,25 s. Evidência preservada: [pytest-initial.xml](evidence/pytest-initial.xml).

1. `test_preferences_accept_and_cancel_are_distinct`: o Qt offscreen avisou que
   não encontrava fontes. Corrigida a configuração de fontes dos testes Windows,
   mantendo avisos como falhas.
2. `test_close_reopen_restores_geometry_docks_and_toolbar_visibility`: a tela
   virtual offscreen era menor que a geometria solicitada; Qt ajustava a janela.
   O teste passou a escolher dimensões coerentes com a tela disponível e com o
   tamanho mínimo. O round-trip também foi comprovado no Windows nativo.
3. `test_opt_out_of_layout_restore_and_reset_layout_are_real`: avisos de
   `propagateSizeHints` e `raise` ao flutuar dock no offscreen. O teste comum cobre
   movimentação entre áreas; o caso flutuante foi separado e passou nativamente.
4. `test_startup_and_diagnostics_do_not_use_network_or_spawn`: a asserção inicial
   confundia `acceptDrops` do QMainWindow, necessário à organização dos docks,
   com suporte a arquivos. A janela agora ignora explicitamente URLs de arquivos;
   o teste envia um evento de arrastar real do Qt e verifica a rejeição e os bytes
   originais. Não havia motor PDF lendo arquivos nessa rodada.

A rodada dirigida de correções teve **22 aprovados e 1 falha**, em 6,84 s:
[pytest-corrections.xml](evidence/pytest-corrections.xml). A falha era um
`DeprecationWarning` no construtor de QDragEnterEvent com QPoint no Qt 6.12.
O teste foi atualizado para QPointF; nenhum aviso foi suprimido para fazê-lo passar.

Rodadas intermediárias completas: **84 aprovados + 1 ignorado** no headless;
depois **86 aprovados** no nativo e **85 aprovados + 1 ignorado** no headless.
Após a proteção adicional do arquivo de configurações, foram executadas as
rodadas finais de **88** e **87 + 1**, cujos XMLs finais estão vinculados acima.

A primeira análise Ruff encontrou 24 problemas de formatação/importação. A
formatação, organização de imports e revisões posteriores resolveram os avisos.
Houve ainda uma linha longa e um desalinhamento no script de inventário durante
sua edição; as verificações finais passaram.

Na revisão de segurança, foi acrescentada a identificação do INI do DocForge:
um PDF ou INI alheio indicado em `--settings-file` não pode ser substituído.
Os testes verificam preservação byte a byte. Falhas físicas de escrita e decisões
do diálogo de fechamento também são testadas separadamente.

## Inspeção visual e execução

O smoke nativo iniciou QApplication/MainWindow reais, abriu abas de ajuda e
diagnóstico, alternou temas, capturou imagens, ocultou painel, fechou/reabriu e
verificou tema e layout. Usou INI temporário, sem modificar preferências do usuário.
Resultado registrado em [smoke.json](evidence/smoke.json).
O catálogo Qt pt-BR foi carregado com sucesso. O caminho padrão conferido nesta
máquina foi `%LOCALAPPDATA%\DocForge\DocForge Ultimate\settings.ini`.

Capturas inspecionadas visualmente:

- [Classic Light](evidence/classic-light.png): menus, três barras, docks, abas,
  fila vazia, status offline, comandos futuros e textos legíveis.
- [Graphite Pro](evidence/graphite-pro.png): paleta escura, contraste e mesmas
  estruturas. Foi corrigido o contraste dos títulos de docks no tema claro.

Essas capturas são da janela Qt nativa e foram geradas por código. Não são um
mockup nem evidência de interação humana. A tentativa de controle interativo via
`computer-use` falhou na inicialização do helper com
`helper_unknown_error: setup refresh had errors`; houve reinicialização e nova
tentativa, sem sucesso. Nenhuma janela foi controlada por esse helper.
Os fluxos funcionais foram executados automaticamente com Qt/pytest-qt.

## Dependências, rede e integridade

Versões, requisitos Python, wheels Windows e licenças foram consultados nas
fontes oficiais antes de fixar as dependências; veja
[ADR 0001](decisions/0001-m0-foundation.md), [avisos](../THIRD_PARTY_NOTICES.md) e
[inventário instalado](evidence/dependencies.json). O texto integral AGPL está
em `LICENSE`. PyMuPDF não foi instalado ou fixado no M0.

A aplicação não possui imports de clientes de rede ou subprocessos. Testes
bloqueiam chamadas externas durante inicialização/diagnóstico e conferem domínio
sem Qt e UI sem motores PDF. Isso é evidência do M0, não auditoria independente
de todas as bibliotecas nativas. As consultas de catálogo e downloads da sessão
foram para preparar o ambiente de desenvolvimento, conforme solicitado.

O executor restrito falhou posteriormente ao criar processos com o mesmo erro
de setup; os comandos locais autorizados foram executados sob a conta do usuário.
O Git recém-criado inicialmente pertencia à conta isolada do executor. Seus
metadados vazios foram preservados em `.cache/git-initial-sandbox` e o repositório
foi reinicializado sob a conta do usuário, sem mudar `safe.directory` global,
sem commits prévios e sem perda de arquivos. `git status` voltou a funcionar.

## Não executado ou fora do escopo

- CI remota: workflow preparado, com ações atuais verificadas e fixadas por
  commit; não houve push nem execução remota observada.
- Python 3.12/3.14: matriz CI preparada; executou-se localmente apenas 3.13.15.
- Windows 10, Ubuntu/Linux, máquina limpa e instalação/desinstalação: não testados.
- DPI alto, múltiplos monitores e leitor de tela: sem validação específica.
- Arrastar painéis com mouse real e avaliação humana completa: pendentes pela
  falha do helper; testes nativos cobrem encaixe, flutuação e restauração por Qt.
- Testes PDF T01–T18 e T20–T22, OCR, segurança documental, performance de PDF e
  instalador: não executados, pois pertencem aos marcos seguintes. T19 foi
  verificado somente quanto às preferências e ao layout existentes no M0.
- Revisão final de artefatos de distribuição, fontes correspondentes, avisos Qt,
  nome/marca e aspectos jurídicos permanecem necessários antes de publicação.

## Checklist verificável do M0

- [x] Git inicializado, ambiente local e `pyproject.toml`/lock reproduzível.
- [x] Código AGPL-3.0-or-later, avisos e dependências documentados.
- [x] Janela Qt real pt-BR, nove menus, três barras com ícones e três docks.
- [x] Abas de ajuda reais, atalhos, preferências e barra de status.
- [x] Classic Light / Graphite Pro em tempo real e persistência local.
- [x] Geometria, visibilidade e organização dos docks/barras restauradas.
- [x] DocumentSession, erros, contratos, registro de tarefas e CapabilitiesService.
- [x] Nenhum recurso PDF anunciado como implementado; comandos futuros desabilitados.
- [x] Configurações não sobrescrevem arquivos não pertencentes ao aplicativo.
- [x] Testes reais nativos/headless e build aprovados; evidências anexadas.
- [x] CI headless configurada e arquitetura/guia/decisões documentados.
- [ ] Aceite humano completo da interface; limitações ambientais acima declaradas.

Execução nesta máquina: `.\.venv\Scripts\python.exe -m docforge`.
Com o ambiente ativado: `python -m docforge`.

**M1 não foi iniciado. Qualquer próximo marco depende da aprovação do usuário.**
