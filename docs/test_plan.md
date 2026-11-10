# Plano de testes do DocForge

## Automação

| Caso M1 | Fluxo observado |
|---|---|
| T01 | Abrir PDF pelo menu, renderizar a primeira página, conferir miniaturas e navegar |
| T02 | Solicitar senha na aba, rejeitar a tentativa errada, abrir com a correta e respeitar a permissão de cópia |
| T03 | Explicar falha de cabeçalho ou corrupção e manter outro PDF disponível |
| T04 | Alternar de 50% a 200%, preservar proporção, ajustar à largura e girar a visualização |
| T05 | Encontrar frase com acentos, saltar entre páginas, realçar e copiar uma seleção |

Casos adicionais cobrem arrastar e soltar, estado independente por aba, lista
de miniaturas sob demanda em documento de 320 páginas, cancelamento, prazo
excedido, conteúdo ativo tratado como conteúdo passivo, migração do INI e
inicialização do processo leitor.

| Caso | Fluxo observado em M2 e M3 |
|---|---|
| T06 | Ordenar entradas de 3 e 5 páginas no diálogo de mesclagem e reabrir a saída de 8 páginas |
| T07 | Dividir `2–4` em três páginas, gerar múltiplas partes e extrair intervalos em ordem escolhida |
| T08 | Reordenar pela miniatura, girar, excluir, desfazer/refazer e verificar ordem e rotação ao reabrir |
| T09 | Cancelar pela fila com exportação em execução, conferir limpeza e repetir a gravação |
| T10 | Pasta ausente, erro de permissão simulado na publicação e destino bloqueado pelo Windows |
| T11 | Escolher salvar, descartar ou cancelar ao fechar uma aba modificada |
| T12 | Marcar texto, inserir objetos, reposicionar comentário em página girada, editar, excluir e reabrir |
| T15 | Cancelar ou confirmar o alerta de assinatura antes de editar ou exportar |
| T22 | Bloquear origem e vínculo físico, exigir confirmação de colisão e preservar backup do destino |

Os casos adicionais de M3 conferem AcroForms, campos com scripts, rolagem
contínua virtualizada e recuperação depois de encerrar o processo de uma aba.
As saídas são reabertas com PyMuPDF e os testes comparam os bytes das entradas.

| Caso | Fluxo observado em M4 |
|---|---|
| T13 | Validar os modelos locais e reconhecer uma digitalização girada em português e em inglês. Conferir busca, aparência e intervalo selecionado |
| T14 | Conferir ação de OCR desabilitada quando faltam modelos e rejeição de modelo incompatível |
| T18 | Abrir dez PDFs, alternar de aba durante um lote, conferir progresso e erros por arquivo e repetir a falha |

Testes adicionais cobrem cancelamento durante conversão, colisão de pasta de
saída, TIFF multipágina, ordem e dimensões das imagens, PNG/JPEG, TXT UTF-8,
extração de imagens compartilhadas, otimização estrutural e redução de imagens,
mesclagem e divisão em lote e confirmação de risco de assinatura. A suíte usa
`DOCFORGE_TEST_TESSDATA` para os dois casos com reconhecimento real.

| Caso | Fluxo observado em M5 |
|---|---|
| T15 | Preservar o aviso antes de editar ou exportar cópias de um PDF assinado |
| T16 | Marcar duas páginas, uma recortada e girada, e exportar. Conferir pixels pretos nas marcas, ausência de texto e de objetos de origem, renderização e preservação dos bytes da entrada |
| T17 | Conferir o aviso da assinatura visual, desenhar ou selecionar imagem e verificar aparência ao reabrir |
| M5 proteção | Validar AES-256, senhas distintas, bits de permissões, autorização de proprietário e ausência de senhas no INI e na fila |
| M5 metadados | Remover Info ou XMP selecionados, preservar campos não selecionados e reabrir cópia criptografada |
| M5 assinatura digital | Assinar PKCS#12 sintético, verificar com e sem raiz local, detectar adulteração e uma revisão posterior com conexões externas bloqueadas no verificador |

Casos adicionais verificam cancelamento da redação durante o progresso,
limpeza das marcas ao mudar de revisão e disponibilidade sem `signing`.

## Regressão do M0

- Inicialização: QApplication real, QMainWindow, nove menus, três barras, três
  docks, QTabWidget, barra de status; módulo executável em processo separado.
- Os comandos de marcos futuros seguem desabilitados e indicam sua etapa.
- Abas internas: abrir uma vez, fechar todas, reabrir Início, reordenar e navegar
  por atalhos e menu Janela, inclusive com barras ocultas.
- Tema: paleta alterada em tempo real; estado do menu e INI correspondentes.
- Configuração: geometria, movimentação e visibilidade de docks/barras após
  fechar/recriar janela; opt-out e restauração padrão; tamanhos e texto dos ícones.
- Preferências: aceitar/cancelar, atalhos configuráveis e prevenção de conflitos.
- Falhas: INI inválido, versão de layout inválida, escrita impossível e decisão
  explícita de cancelar a saída ou descartar somente as preferências.
- Domínio: fonte preservada, isolamento de estado entre sessões, invariantes.
- Tarefas: transições, progresso, snapshots, concorrência, cancelamento sem
  publicação de saída parcial e registro de falha.
- Capacidades: dependências presentes/ausentes, sem habilitar recurso futuro,
  sem subprocessos/rede; certificados não inspecionados.
- Os testes de fronteira verificam domínio independente de Qt, UI sem import
  do motor PDF e rejeição de URLs remotas. A leitura usa o processo local.

## Verificação visual e de execução

1. Iniciar a janela no Windows com preferências de teste separadas.
2. Conferir Classic Light e Graphite Pro, texto, contraste, organização e menus.
3. Abrir um PDF de referência e conferir a página, as miniaturas e as propriedades.
4. Ocultar/mover painel, fechar e reiniciar; conferir persistência.
5. Buscar texto, navegar por ocorrência, girar a visualização e fechar a aba.
6. Conferir a prévia, o painel Edição, a fila de exportação e a rolagem contínua.
7. Capturar mensagens Qt e verificar abertura e exportação a partir do wheel instalado.
8. Conferir marcas e confirmação da redação, aviso da assinatura visual e
   relatório da assinatura criptográfica com raiz de teste.

O relatório distingue interação por controle de janela de testes automatizados.
Screenshots geradas por código não serão descritas como interação humana.

## Casos posteriores

T20 e T21 pertencem a marcos posteriores. T19 é coberto por
preferências e layout. Windows 10, Linux, leitor de tela e múltiplos monitores
exigem ambientes próprios de validação.
