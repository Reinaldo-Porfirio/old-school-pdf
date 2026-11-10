# Old School PDF

> Grátis para sempre. Sem assinatura, sem cadastro, sem nuvem. Você baixa e é seu.

![Old School PDF com o visual Clássico 2000](docs/evidence/classico-2000-pdf.png)

Aplicativo desktop livre para ler, organizar e editar PDFs locais. Abra documentos
em abas, mescle e reorganize páginas, adicione anotações, preencha campos AcroForm
compatíveis e grave uma cópia. Use miniaturas, rolagem contínua, busca e zoom.
Converta imagens, extraia conteúdo, otimize PDFs e processe lotes. O OCR local
é habilitado com modelos de idioma validados pelo usuário.
A aba **Segurança** reúne metadados, proteção AES-256, redação rasterizada e
assinatura visual. Assinatura e verificação criptográficas são opcionais.
A interface usa o visual **Clássico 2000**: relevo 3D, barras de título em
degradê, ícones coloridos, menus completos, atalhos configuráveis e painéis
reorganizáveis. Nada de minimalismo.

O projeto se chamava **DocForge Ultimate** até a versão 0.5.0. Os registros
históricos em `docs/decisions` e `docs/test_report.md` mantêm o nome antigo.

## Executar no Windows

Requer Windows x64 e Python >=3.12,<3.15. O ambiente de teste foi Windows 11
com Python 3.13.15. A instalação inclui o motor PyMuPDF 2.1. Consulte o
[relatório de testes](docs/test_report.md).

Com [uv](https://docs.astral.sh/uv/), na pasta do projeto:

```powershell
uv sync --frozen
uv run --no-sync python -m oldschoolpdf
```

Para incluir assinatura e verificação digitais, instale o extra opcional.

```powershell
uv sync --frozen --extra signing
uv run --no-sync python -m oldschoolpdf
```

A primeira instalação baixa Python e pacotes. Depois dela, o aplicativo funciona
offline. Use o ambiente preparado para abrir a janela ou passar um
caminho de PDF direto na linha de comando.

```powershell
.\.venv\Scripts\python.exe -m oldschoolpdf
.\.venv\Scripts\python.exe -m oldschoolpdf "D:\Documentos\Relatório.pdf"
```

Com Python já instalado, alternativa sem uv:

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e .
.\.venv\Scripts\python.exe -m oldschoolpdf
```

Após ativar `.venv\Scripts\Activate.ps1`, o comando é `python -m oldschoolpdf`.
É possível usar um arquivo separado de preferências:
`python -m oldschoolpdf --settings-file C:\pasta\preferencias.ini`.
Para um diagnóstico de inicialização que abre a janela, grava as preferências
e encerra automaticamente: `python -m oldschoolpdf --smoke-test`.
Use `--settings-file` com um caminho de teste para preservar sua organização atual.

## Ler e editar PDFs

- Use `Ctrl+O` ou solte PDFs locais na janela. Cada arquivo abre em uma aba e
  pede a senha na própria aba quando necessário.
- Clique em uma miniatura, informe a página ou pressione `Page Up` e `Page Down`.
  Use a lista de zoom, os botões de ajuste ou `Ctrl` com a roda do mouse.
- Abra a busca com `Ctrl+F`. Pressione `Enter` para procurar e navegue com `F3` e
  `Shift+F3`. A busca usa a camada de texto do documento.
- Arraste sobre o texto com a seleção por área ativada. `Ctrl+C` copia a área ou
  a página inteira quando o PDF permite cópia.
- Em **Documento**, mescle PDFs e revise a ordem e a contagem de páginas. Divida
  ou extraia intervalos como `2–4,6–8`. Arraste miniaturas para reordenar ou use
  o menu Documento para mover, girar e excluir páginas da cópia de trabalho.
- Em **Editar > Anotações** ou no painel **Edição**, escolha a ferramenta e
  indique a área na página. Selecione uma anotação para mover, editar o texto
  ou excluí-la conforme o tipo. O comando **Preencher formulário** lista os
  campos da página atual.
- **Ctrl+Z** e **Ctrl+Y** percorrem as revisões. **Ctrl+Shift+S** grava um PDF
  separado. Um asterisco indica alterações pendentes. A fila permite cancelar
  exportações antes da publicação.
- **Exibir > Rolagem contínua** permite percorrer várias páginas no mesmo painel.
- `F1` abre a ajuda local. A lista de atalhos está em **Ferramentas > Preferências**.

## Proteger, redigir e assinar cópias

- **Remover metadados** permite escolher campos da ficha Info e apagar o XMP
  completo. A operação preserva o conteúdo das páginas, campos e anexos.
- **Proteger cópia com senha** grava AES-256 com senhas distintas de abertura
  e proprietário. A autorização de proprietário é exigida para mudar a
  proteção ou os metadados de um PDF já criptografado.
- **Marcar área para redação** e **Exportar redação rasterizada** geram um PDF
  novo com páginas em imagens de 150 DPI. Revise todas as ocorrências visíveis
  antes de exportar. A cópia perde texto pesquisável, OCR, links, formulários
  e assinaturas. Aceita PDFs sem criptografia de até 100 páginas.
- **Inserir assinatura visual** coloca um desenho ou PNG/JPEG como anotação.
  A assinatura visual é uma marca gráfica sem verificação criptográfica.
- Com `signing`, **Assinar digitalmente uma cópia** usa PKCS#12 local.
  **Verificar assinaturas digitais** mostra integridade, cobertura e confiança
  baseada nas raízes X.509 fornecidas. A avaliação é offline.

O INI de preferências fica em
`%LOCALAPPDATA%\Old School PDF\settings.ini`. O caminho efetivo
aparece em **Local e privacidade**. Ele guarda aparência, atalhos, organização
da janela e limites de leitura. Página, zoom e revisões ficam na sessão da
aba. A gravação atômica exige a identificação do Old School PDF em arquivos INI
preexistentes e preserva outros arquivos indicados por engano.

## Desenvolvimento e testes

Antes da suíte, defina `OLDSCHOOLPDF_TEST_TESSDATA` como a pasta que contém os
modelos `por.traineddata` e `eng.traineddata` se quiser executar o OCR real.
A ausência dessa variável deixa somente os casos com reconhecimento real
fora da suíte. O teste de OCR indisponível continua ativo.
Sem o extra `signing`, o caso com certificado sintético é ignorado e o
teste de disponibilidade dos comandos continua ativo.

```powershell
uv sync --frozen --extra signing
uv run --no-sync ruff check .
uv run --no-sync ruff format --check .
$env:QT_QPA_PLATFORM = 'offscreen'
uv run --no-sync pytest -v
uv run --no-sync python -m build --no-isolation
```

`offscreen` serve para testes headless. Remova a variável para abrir a janela
normal: `Remove-Item Env:QT_QPA_PLATFORM -ErrorAction SilentlyContinue`.
Os testes usam arquivos temporários, não as preferências reais. A CI configura
Windows e Python 3.12/3.13/3.14; execução na CI só é comprovada após subir o projeto
e observar o resultado. Linux, Windows 10 e instaladores ainda não foram validados.

## Estrutura e documentação

- `src/oldschoolpdf/domain`: modelos e invariantes sem Qt.
- `src/oldschoolpdf/application`: contratos e serviços, sem widgets.
- `src/oldschoolpdf/infrastructure`: QSettings, inspeção local e processos PDF.
- `src/oldschoolpdf/ui`: janela, painéis, diálogos, tema e ícones SVG próprios.
- [Conceitos visuais](docs/concepts/README.md) que deram origem ao tema Clássico 2000.
- [Arquitetura](docs/architecture.md), [decisões do M5](docs/decisions/0005-m5-security.md),
  [plano de teste](docs/test_plan.md), [relatório real](docs/test_report.md),
  [guia offline](docs/user_guide.md), [especificação integral](docs/product_spec.md).

Código sob **AGPL-3.0-or-later**, com PyMuPDF pela opção AGPLv3.
Consulte [LICENSE](LICENSE) e [avisos de terceiros](THIRD_PARTY_NOTICES.md).
