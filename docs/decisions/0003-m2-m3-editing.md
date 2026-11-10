# ADR 0003 · Revisões, organização e edição local

**09/11/2026** · M2 e M3 · Aceita.

## Motor e distribuição

O processo local existente mantém PyMuPDF 2.1 com MuPDF 1.28.6. O desktop usa
PySide6 Essentials 6.12.0. M2 e M3 usam as mesmas dependências fixadas no M1.
As condições de distribuição do código e das bibliotecas permanecem em
[avisos de terceiros](../../THIRD_PARTY_NOTICES.md) e [ADR 0002](0002-m1-viewer.md).

## Revisões

As operações reabrem a revisão corrente em outro objeto `Document`. Cada edição
grava um PDF temporário, sincroniza os bytes e reabre a saída. A revisão só muda
após essa verificação. A origem é acessada em leitura e sua identidade é conferida
quando o histórico a reabre. O histórico mantém até 40 revisões, com orçamento de
256 MiB para as anteriores às duas mais recentes. A pasta temporária é removida
no fechamento normal da aba. Se um processo PDF encerrar, a aba pode recuperar
a última revisão confirmada e iniciar um histórico novo.

O diário interno do MuPDF foi ensaiado com rotação, extração de texto e campos.
As operações de campo e as alterações implícitas durante algumas leituras
produziram estados divergentes no desfazer. Snapshots custam I/O proporcional ao
PDF e preservam um estado verificável para páginas, anotações e formulários.
[API Document do PyMuPDF](https://pymupdf.readthedocs.io/en/latest/document.html)

## Publicação e cancelamento

Cada PDF é preparado em arquivo temporário exclusivo na pasta escolhida. A
validação verifica abertura, contagem de páginas, proteção e carregamento da
primeira e da última página. A publicação cria o arquivo de destino sem substituir
nomes surgidos durante o processamento. Para um destino existente confirmado, um
vínculo físico preserva a versão anterior com nome único antes da troca atômica.
A substituição depende de suporte a vínculos físicos na unidade. A falha preserva
o destino. A origem e seus vínculos físicos são protegidos em todos os casos.

Divisão em várias partes valida todos os temporários antes de publicar. Se uma
publicação falhar, o aplicativo tenta reverter somente saídas que acabou de criar
e cuja identidade ainda confere. A troca de nome é atômica por arquivo. A fila
aplica cancelamento antes da publicação e limpa temporários após a operação ou
interrupção do processo dedicado de mesclagem.

## Compatibilidade de edição

- A mesclagem aceita PDFs sem criptografia e inclui páginas, anotações, campos e
  links compatíveis. Marcadores globais, anexos e metadados de cada entrada ficam
  nos respectivos originais. Em uma aba protegida, os comandos respeitam as
  permissões e a exportação conserva a criptografia da revisão.
- A reordenação mantém o catálogo e os campos do PDF. Divisão e extração
  preservam o registro AcroForm das páginas incluídas e desvinculam os campos
  omitidos. Quando há campos descartados, a ordem de cálculo é removida. Saídas
  parciais preservam os campos AcroForm compatíveis e deixam o XFA na origem.
- Anotações usam objetos PDF próprios. Caixas de texto usam a fonte padrão
  Helvetica. Imagens PNG e JPEG são anotações com aparência de imagem, limitadas
  a 12 MiB e 16 milhões de pixels. Marcações se vinculam à camada de texto.
  A seleção do aplicativo apresenta até 300 anotações e 300 campos por página.
- Campos AcroForm simples de texto, caixa de marcação, rádio e escolhas podem
  ser atualizados quando compatíveis. Campos com scripts, leitura restrita,
  senhas, multisseleção, formatos complexos e formulários XFA ficam em leitura
  passiva. JavaScript do documento permanece desabilitado no processo.
- O alerta de assinatura usa indicadores do PDF e do MuPDF. A aba pede confirmação
  antes de editar ou exportar com esse indicador. A validação criptográfica e
  a assinatura de documentos pertencem ao M5.
- A rolagem contínua virtualiza linhas e requisita as imagens visíveis. Busca,
  zoom explícito e posicionamento de anotações usam a página individual.

[API Page do PyMuPDF](https://pymupdf.readthedocs.io/en/latest/page.html) ·
[API Widget do PyMuPDF](https://pymupdf.readthedocs.io/en/latest/widget.html)
