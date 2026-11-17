# Alterações

## 0.9.1 · 17/11/2026

Correções na edição do texto original, achadas com PDFs reais gerados pelo Word e pelo Edge.

- **Largura do bloco:** um bloco de uma linha tinha a largura e a altura exatas do texto
  antigo, então qualquer palavra a mais "não cabia". Agora o bloco usa primeiro a largura livre
  ao lado (até a margem do texto ou o próximo objeto da linha) e uma folga de altura, antes de
  reduzir a fonte. Títulos centralizados continuam centralizados; alinhados à direita crescem
  para a esquerda.
- **Tabelas e listas:** o MuPDF juntava a tabela inteira, ou uma linha dela, num bloco só, e
  editar desmanchava as colunas. Agora cada célula é um bloco separado.
- **Continuação em página nova:** as páginas novas usam a largura da coluna de texto, em vez da
  largura de uma célula estreita, e títulos não são mais picotados em várias páginas.
- **Prévia:** a aba de prévia fica sempre disponível. Mostra as páginas de continuação com
  botões de navegação, explica na própria área quando a prévia falha e avisa quando ficou
  desatualizada depois de mudar o texto ou as opções.
- O MuPDF às vezes dizia que o texto cabia e descartava as últimas linhas; agora o texto escrito
  é conferido antes de gravar e, se faltar algo, o programa tenta reduzir ou responde que não
  coube, com uma mensagem que aponta as opções.
- Fontes em coleções `.ttc` (como a Cambria, usada pelo Word) passam a ser encontradas.
  Quando uma fonte instalada troca letras na leitura (ligaduras como "fi"), o bloco usa a fonte
  padrão parecida, para o texto continuar pesquisável e copiável.
- Com "Expandir o bloco para baixo" marcado, o bloco cresce antes de reduzir a fonte.

## 0.9.0 · 17/11/2026

- **Converter para Word (.docx)**, com conversor próprio e offline: parágrafos com fonte,
  tamanho, negrito, itálico e cor; linhas e hifenização reunidas em parágrafos; títulos com os
  estilos do Word; tabelas com grade; imagens; links; uma página do Word para cada página do PDF,
  com o mesmo tamanho e orientação. Páginas com OCR viram texto; digitalizações sem OCR entram
  como imagem e o relatório avisa. O arquivo gravado é reaberto e conferido. Funciona em lote.
- **Marcadores (sumário)**: a aba Índice mostra os marcadores e leva à página com um clique;
  o editor adiciona, renomeia, muda a página, reordena e monta níveis, e sugere um sumário
  pelos títulos do texto, ignorando cabeçalhos repetidos. Destinos exatos, links externos, cores
  e estilos dos marcadores existentes são preservados; a gravação é conferida.
- **Páginas**: inserir páginas em branco (mesmo tamanho da atual, A4, A5, Carta ou Ofício);
  cortar margens (automático, medidas fixas ou restaurar o tamanho original), com aviso de que a
  área cortada continua no arquivo; mudar o tamanho do papel, centralizando o conteúdo sem
  distorcer e levando junto anotações, links e campos, em páginas giradas ou já cortadas. O texto
  de cada página é conferido antes e depois.
- **Criar campos de formulário** desenhando na página: texto, texto de várias linhas, caixa de
  marcar e lista suspensa, com nome único, dica, valor inicial, limite de caracteres e
  preenchimento obrigatório. Campos em páginas giradas saem na orientação certa. Também é
  possível excluir campos.
- **Edição de texto**: nova opção para continuar o texto que não couber em páginas novas,
  inseridas logo depois da atual, sem reduzir a fonte. Cada página nova é conferida.
- O relatório do lote ganhou o botão **Abrir pasta do resultado**.
- Permissões do PDF respeitadas em todas as operações novas: montar o documento para páginas e
  marcadores, alterar o conteúdo para corte e tamanho, alterar conteúdo e anotações para campos.

## 0.8.1 · 14/11/2026

- Correção: ao fechar uma aba editada, o programa espera o processo do PDF terminar antes de
  apagar a pasta temporária de revisões e tenta de novo por alguns segundos se o Windows ainda
  a mantiver presa. Em máquinas lentas, a 0.8.0 podia deixar essa pasta em %TEMP%.

## 0.8.0 · 14/11/2026

Inclui o que estava planejado para a 0.7, que não foi publicada separadamente.

- **Impressão** (Ctrl+P): diálogo do sistema com intervalo, página atual, cópias e ordem; páginas
  renderizadas na resolução da impressora (até 300 DPI, ou 150 DPI quando o PDF só permite
  impressão em baixa qualidade), ajustadas ao papel e giradas quando a orientação difere; tarefa
  na fila com progresso e cancelamento; respeita a permissão de impressão do PDF.
- **Edição do texto original** (Ctrl+E): editor lado a lado com a página e os blocos numerados,
  negrito e itálico, vários blocos por vez, prévia verificada e aplicação como revisão desfazível.
- Motor de edição com verificações: remoção só da faixa central das letras, conferência de que
  nenhum texto vizinho foi afetado, escrita numa página gêmea com fontes reduzidas a subconjunto,
  reanexação de links, conferência do texto gravado, da cor visível, dos pixels fora da área, dos
  links e das anotações. Qualquer divergência cancela a edição.
- Fontes: a mesma família instalada no Windows substitui fontes em subconjunto, respeitando a
  permissão de incorporação de cada fonte; sem ela, uma fonte padrão parecida.
- Texto que não cabe: reduzir até 85% ou 70% e expandir o bloco para baixo até o próximo conteúdo.
- Recusas explicadas: texto invisível de OCR, girado, sobre campo de formulário, da direita para
  a esquerda, e PDFs sem permissão de alterar conteúdo.
- A janela principal usa o ícone do aplicativo.

## 0.6.1 · 10/11/2026

- O executável e o instalador passam a incluir os textos da LGPL-3.0 e da GPL-3.0 (Qt),
  a licença do Python e os arquivos de licença de cada biblioteca empacotada.
- README com links diretos de download, requisitos, verificação por SHA-256 e passo a passo
  do OCR. THIRD_PARTY_NOTICES documenta a distribuição binária.

## 0.6.0 · 10/11/2026 · Old School PDF

- Novo nome: DocForge Ultimate passa a se chamar **Old School PDF**. Pacote `oldschoolpdf`,
  comando `python -m oldschoolpdf` e preferências em `%LOCALAPPDATA%\Old School PDF`.
- Tema único **Clássico 2000**, com o estilo nativo "Windows" do Qt, paleta cinza com relevo 3D,
  fonte Tahoma e painéis com barra de título em degradê azul-marinho.
- Ícones redesenhados em SVG, coloridos e com degradês, e ícone próprio da janela.
- Temas antigos salvos no INI voltam ao padrão sem descartar as outras preferências.
- A página inicial mostra o novo roteiro, sem o selo do marco, e o título da janela deixa
  de exibir o marco interno.
- Instalador para Windows (`OldSchoolPDF-0.6.0-setup.exe`, Inno Setup com assistente clássico):
  instalação por usuário sem administrador, atalhos, entrada opcional em "Abrir com" para PDFs
  e desinstalação completa. Inclui a assinatura digital.
- Executável gerado com PyInstaller por `packaging/build.py`, que também testa a abertura e o
  leitor de PDF empacotado. O próprio executável vira o processo leitor com `--pdf-worker`.
- O motor tolera a ausência do módulo opcional de layout do PyMuPDF, que fica fora do pacote.

## 0.5.0 · 10/11/2026 · M5

- Remoção seletiva de Info e XMP em cópias e proteção AES-256 com senhas distintas.
- Marcas revisáveis e exportação para redação rasterizada com auditoria dos pixels e da estrutura.
- Assinatura visual por desenho ou imagem, com distinção na interface.
- Extra `signing` para assinatura PKCS#12 e relatório de verificação criptográfica offline.
- Menu e painel Segurança, atalho configurável de redação e ajuda local atualizada.
- Nova tentativa de limpeza quando o Windows mantém temporários de um lote cancelado bloqueados.

## 0.4.0 · 10/11/2026 · M4

- OCR local opt-in com validação dos modelos de português e inglês.
- Camada pesquisável invisível nas páginas selecionadas de PDFs digitalizados.
- Exportação PNG/JPEG, importação de imagens e TIFF multipágina, extração TXT e imagens incorporadas.
- Compactação estrutural e redução opcional de imagens, com comparação de tamanho.
- Fila por entrada, progresso, cancelamento, relatório e repetição de falhas e canceladas.

## 0.3.0 · 09/11/2026 · M2 e M3

- Mesclagem, divisão, extração, reordenação por miniaturas, rotação e exclusão de páginas.
- Exportação com validação, proteção da origem, confirmação de colisões e backup do destino substituído.
- Desfazer/refazer, aviso de alterações ao fechar e recuperação da última revisão na aba.
- Destaques, sublinhados, comentários, caixas de texto, carimbos, formas e imagens como anotações.
- Preenchimento de campos AcroForm compatíveis e alerta sobre possível invalidação de assinatura digital.
- Rolagem contínua com carregamento das páginas visíveis.

## 0.2.0 · 09/11/2026 · M1

- Leitura local de PDFs em abas com miniaturas, zoom, navegação e rotação visual.
- Busca com acentos, navegação por ocorrências e cópia da página ou da seleção.
- Entrada por menu, arrastar e soltar e argumento de linha de comando.
- Senha na aba, falhas de leitura explicadas e operações em processos separados.
- Fila de aberturas e buscas, cache configurável e preservação das preferências M0.

## 0.1.0 — 04/11/2026 — M0

- Estrutura Python/Qt Widgets local com domínio, serviços, infraestrutura e UI.
- Menus clássicos, barras com ícones próprios, docks, abas de ajuda e status.
- Temas Classic Light / Graphite Pro, preferências e persistência de layout.
- Atalhos configuráveis, ajuda offline e diagnóstico de dependências locais.
- Contratos de documentos/renderização/tarefas e registro cooperativo de tarefas.
- Qualidade, testes pytest/pytest-qt e workflow CI Windows headless.
- Código AGPL-3.0-or-later e avisos de dependências; nenhum instalador.
- Nenhuma operação PDF, OCR, conversão ou assinatura implementada neste marco.
