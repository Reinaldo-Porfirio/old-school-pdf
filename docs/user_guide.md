# Guia do Old School PDF

Abra o Old School PDF com `python -m oldschoolpdf`. Pressione **Ctrl+O**, use
**Arquivo > Abrir PDF** ou solte arquivos locais na janela. A abertura mostra
o progresso na aba e na fila. PDFs protegidos pedem a senha na aba e permitem
nova tentativa. Fechar a aba cancela a abertura.

## Ler e encontrar informações

- Selecione uma miniatura, use o número acima da página ou pressione **Page Up**
  e **Page Down**. O painel de propriedades mostra o formato, a página, as
  dimensões e os metadados disponíveis.
- Ajuste à página ou à largura pela barra superior. Selecione uma porcentagem
  ou use **Ctrl** com a roda do mouse. **Girar visualização 90°** muda a
  orientação na aba. Desative a seleção por área para arrastar a página ampliada.
- Ative **Exibir > Rolagem contínua** para percorrer várias páginas com a roda
  do mouse. Buscar texto ou escolher uma ferramenta de anotação volta à página individual.
- Abra **Ctrl+F**, digite o texto e pressione **Enter**. **F3** e **Shift+F3**
  percorrem as ocorrências e saltam para a página correspondente. **Parar**
  interrompe a busca. Em PDFs digitalizados, a busca depende de uma camada de
  texto já existente.
- Com **Selecionar área de texto** ativo, arraste um retângulo sobre a página e
  pressione **Ctrl+C**. Sem seleção, a cópia lê o texto da página. A disponibilidade
  segue a permissão de cópia do PDF.

Cada aba mantém a página, o zoom e a rotação enquanto estiver aberta. Use
**Ctrl+W** para fechar uma aba, **Ctrl+Tab** para alternar e **Janela** para
escolher uma diretamente.

## Organizar páginas

- Em **Documento > Mesclar PDFs**, adicione arquivos, revise a ordem e o total
  de páginas e escolha o destino. A mesclagem aceita PDFs sem criptografia.
- Em **Dividir PDF**, indique um intervalo por saída. Por exemplo, `2–4,6–8`
  gera `nome-01.pdf` e `nome-02.pdf`. Use **Extrair páginas** para gravar esses
  intervalos em um único PDF na ordem informada.
- Arraste uma miniatura para a nova posição ou use **Reordenar páginas**. Use
  **Girar páginas do PDF** para gravar a orientação e **Excluir páginas** para
  remover intervalos da cópia de trabalho. A aba mostra a revisão atual.
- **Inserir páginas em branco** coloca de 1 a 50 páginas antes ou depois da atual, no tamanho
  dela ou em A4, A5, Carta ou Ofício, em retrato ou paisagem.
- **Cortar margens** remove as bordas em branco (com uma folga escolhida), corta medidas fixas
  de cada lado ou restaura o tamanho original. A área cortada deixa de aparecer e de ser
  impressa, mas continua no arquivo. Para apagar informação, use a redação.
- **Mudar o tamanho do papel** leva as páginas escolhidas para A4, A5, Carta ou Ofício. O
  conteúdo é ampliado ou reduzido na mesma proporção e centralizado. Texto, links, anotações e
  campos acompanham, e o texto continua editável.

## Marcadores (sumário)

- A aba **Índice** do painel Páginas e índice mostra os marcadores. Clique em um para ir à
  página. Marcadores sem destino, como os de páginas excluídas, aparecem com um aviso.
- **Documento > Marcadores** abre o editor: adicione um marcador da página atual, mude o título
  e a página, use **Subir** e **Descer** para a ordem e **Recuar** e **Avançar** para os níveis.
  Clique duas vezes num marcador para ver a página.
- **Sugerir pelos títulos do texto** procura linhas curtas com fonte maior que o texto comum e
  monta até 300 marcadores em três níveis, ignorando cabeçalhos e rodapés repetidos. Escolha
  substituir a lista ou acrescentar ao final.
- Marcadores existentes mantêm o destino exato, links externos, cor e estilo quando a página não
  muda. Se o PDF mudou desde a abertura do editor, a gravação é recusada para não perder nada.

## Anotar e preencher

- Abra **Editar > Anotações** ou **Propriedades e ferramentas > Edição**.
  Arraste sobre texto para destacar, sublinhar ou riscar. Clique para inserir um
  comentário. Caixas de texto, carimbos, formas e imagens usam uma área arrastada.
  **Esc** encerra a ferramenta de posicionamento.
- **Caneta**, **Inserir linha** e **Inserir seta** desenham com o mouse. A barra sobre a página
  escolhe a cor (azul, vermelho, preto, verde ou amarelo marca-texto) e a espessura, que valem
  também para retângulos e elipses. Com a caneta, faça vários traços e pressione **Enter** ou
  **Gravar desenho**; **Apagar último traço** desfaz o anterior. Linhas, setas e desenhos podem
  ser movidos depois, como as outras anotações.
- Selecione a anotação na página ou na lista do painel Edição. As opções de
  mover, editar texto e excluir dependem do tipo e das permissões do objeto.
- **Documento > Preencher formulário** permite editar campos AcroForm da página
  atual. Campos com scripts ou formato incompatível permanecem em leitura passiva.
- **Documento > Criar campo de formulário**: arraste o retângulo do campo na página e escolha
  texto de uma linha, texto de várias linhas, caixa de marcar ou lista suspensa. O nome precisa
  ser único no documento. Dica, valor inicial, limite de caracteres, tamanho da letra e
  preenchimento obrigatório são opcionais. **Excluir campo de formulário** remove um campo da
  página atual.
- PDFs com indicação de assinatura digital pedem confirmação antes da edição ou
  exportação. A janela informa o risco de invalidar a assinatura na cópia.

## Editar o texto original

Use **Editar > Editar texto do PDF** (Ctrl+E). A página aparece à esquerda com os blocos de
texto numerados; clique num bloco ou escolha na lista. Edite o texto à direita. **Negrito** e
**Itálico** valem para o trecho selecionado. Altere quantos blocos quiser e use **Gerar
prévia** para ver a cópia editada na aba ao lado. **Aplicar ao PDF** grava uma revisão nova,
desfeita com Ctrl+Z, e **Restaurar bloco** desfaz as mudanças de um bloco antes de aplicar.

Se o texto novo não couber, o bloco usa primeiro a largura livre ao lado, até a margem do
texto ou o próximo objeto da linha. Depois, escolha reduzir a fonte até 85% ou 70% ou expandir
o bloco para baixo, até o próximo conteúdo. Com **Continuar o restante numa página nova**, o bloco ocupa o
espaço livre abaixo dele sem reduzir a fonte e o texto que sobrar segue em páginas novas,
inseridas logo depois da atual (até 20 páginas por edição). Na aba de prévia, use
**Página anterior** e **Próxima página** para conferir as páginas de continuação. Células de
tabela e itens de lista aparecem como blocos separados. A opção **Usar as fontes instaladas no Windows** deixa o
resultado mais fiel ao original. Blocos tracejados não podem ser editados; passe o mouse sobre
eles na lista para ver o motivo. Páginas digitalizadas não têm texto editável.

Antes de gravar, o programa confere o texto escrito, o restante da página, a cor, os links e
as anotações. Se algo divergir, aparece uma mensagem e nada é alterado.

## Localizar e substituir

**Editar > Localizar e substituir** (Ctrl+H) procura uma palavra ou frase no texto do PDF, em
todas as páginas ou só na atual, com opções para diferenciar maiúsculas e para palavras
inteiras. A lista mostra cada ocorrência com o trecho ao redor; desmarque o que não quiser
trocar e clique em **Substituir marcadas**. Deixe o campo do texto novo em branco para apagar.

A troca usa o mesmo motor da edição de texto: mantém a fonte, usa o espaço livre ao lado e
reduz a fonte até 85% se o texto novo for maior. O que não couber fica como estava e aparece
num aviso com a página e o motivo. Ctrl+Z desfaz todas as trocas de uma vez.

## Numeração, cabeçalho, rodapé e marca d'água

**Documento > Numeração, cabeçalho e rodapé** escreve textos no topo e no pé das páginas, à
esquerda, no centro ou à direita. Marque **Numerar as páginas** e escolha o formato (Página 1
de 10, 1/10, - 1 - e outros) e a posição. Os botões **Número da página**, **Total de
páginas**, **Data de hoje** e **Nome do arquivo** inserem campos que mudam em cada página.
Para não numerar a capa, escolha as páginas 2 em diante e comece em 1. A prévia mostra o topo
e o pé da primeira página em tamanho real. O texto entra no conteúdo da página e continua
pesquisável. Se ele encostar em algo que já existia, o programa avisa em quais páginas.

**Documento > Marca d'água** aplica um texto ou uma imagem em todas as páginas escolhidas,
com cor, direção, tamanho automático ou fixo, opacidade e camada (atrás ou na frente do
conteúdo). A marca de texto vira desenho vetorial: não aparece na busca, na cópia de texto nem
na conversão para Word, e não atrapalha a edição do texto. Em páginas digitalizadas, escolha
**Na frente do conteúdo**; o programa avisa quando a marca ficou escondida.

Aplicar de novo substitui o cabeçalho ou a marca d'água anterior. **Remover cabeçalho, rodapé
e marca d'água** tira o que o programa aplicou, mesmo depois de salvar e reabrir o PDF. O texto
do cabeçalho aparece no editor de texto como bloco não editável, com a indicação de usar o
comando de numeração para mudá-lo.

## Imprimir

**Arquivo > Imprimir** (Ctrl+P) abre o diálogo do Windows. Escolha a impressora, o intervalo,
a página atual ou todas, as cópias e a ordem. Cada página é ajustada ao papel. A impressão
aparece na fila de tarefas, onde pode ser cancelada.

## Gravar e fechar

**Ctrl+Z** e **Ctrl+Y** alternam entre as revisões. A aba marca alterações pendentes
com um asterisco. **Arquivo > Salvar como** grava a revisão em outro caminho e
mantém a origem. Para substituir outro PDF, confirme a criação do backup.
A fila indica o resultado e permite cancelar enquanto a exportação está em execução.
Ao fechar uma aba modificada, escolha salvar, descartar ou cancelar.

Se o processo do PDF falhar com a aba aberta, **Recuperar revisão** reabre a
última cópia validada e começa o histórico a partir dela.

## OCR local

1. Abra **OCR > Configurar OCR local**. Escolha a pasta `tessdata` de uma
   instalação confiável ou com modelos oficiais `por.traineddata` e `eng.traineddata`.
   É possível configurar apenas um idioma. [Modelos oficiais do Tesseract](https://tesseract-ocr.github.io/tessdoc/Data-Files)
2. Clique em **Testar modelos**. Confirme **Usar modelos validados** quando
   aparecerem os idiomas aprovados.
3. Em **OCR > Reconhecer texto**, confira a entrada, selecione idioma, DPI,
   páginas e pasta de saída. A prévia mostra a página aberta quando a entrada
   sugerida está na lista. A caixa de páginas aceita `2–4,6–8`.
4. Adicione à fila. Quando a tarefa terminar, abra o PDF pelo **Relatório do
   lote** e use **Ctrl+F** para conferir palavras reconhecidas.

Páginas com texto existente são puladas. A camada invisível preserva o conteúdo
visual das páginas processadas. Trechos reconhecidos podem conter erros, sobretudo
em imagens de baixa resolução, inclinadas ou manuscritas.

## Conversão, otimização e lotes

- **Ferramentas > Reunir imagens em PDF** aceita PNG, JPEG e TIFF, inclusive
  TIFF com várias páginas. Use **Subir** e **Descer** para conferir a ordem.
- **Exportar PDF como imagens** gera PNG ou JPEG no DPI escolhido. **Extrair texto
  UTF-8** gera um TXT separado por página e **Extrair imagens incorporadas** grava
  imagens disponíveis no PDF sem repetir o mesmo objeto.
- **Converter para Word (.docx)** gera um documento editável com parágrafos, fontes, negrito,
  itálico, cores, títulos com estilos do Word, tabelas com grade, imagens e links, e uma página
  do Word por página do PDF. Páginas com OCR viram texto; digitalizações sem OCR entram como
  imagem. O resultado segue o fluxo do texto: colunas, caixas posicionadas e desenhos vetoriais
  podem mudar de lugar ou ficar de fora.
- **Otimizar PDF** compacta a estrutura. Marque a redução de imagens se aceitar
  recompressão com perda. O relatório compara os tamanhos e a cópia é publicada
  quando houver redução.
- **Processar lote** também permite dividir PDFs em partes consecutivas e
  mesclar uma lista ordenada. O lote lê os arquivos salvos no disco. Use
  **Salvar como** para processar uma revisão que ainda esteja na aba.
- O lote grava cada resultado em uma pasta nova. A fila aceita cancelamento por
  tarefa ou por lote. O relatório permite abrir o PDF gerado, abrir a pasta do resultado, copiar os detalhes
  e repetir somente falhas e canceladas. Resultados concluídos continuam na saída.

O processamento em lote aceita PDFs sem criptografia. Para gerar uma cópia
modificada de um PDF com indicação de assinatura, confirme o aviso no diálogo.

## Segurança e assinaturas

Abra o menu **Segurança** ou a aba **Segurança** do painel direito.

1. Em **Remover metadados**, selecione os campos da ficha Info e, se desejar,
   o pacote XMP completo. Selecionar todos os campos remove a ficha Info.
   Comentários, anexos e informações visíveis na página ficam fora dessa limpeza.
2. Em **Proteger cópia com senha**, informe e repita as senhas de abertura e de
   proprietário. Marque as permissões que deseja conceder a quem tem a senha
   de abertura. Leitores de PDF interpretam essas restrições. Para mudar a
   proteção ou limpar metadados de um PDF criptografado, autorize como proprietário.
3. Para expurgar áreas visíveis, use **Marcar área para redação** ou **Ctrl+Alt+R**.
   Arraste sobre toda a área sensível. Repita para outras regiões e páginas.
   **Desmarcar última área** remove a última marca. Se editar ou desfizer a
   revisão, marque as regiões novamente.
4. Em **Exportar redação rasterizada**, revise a lista de páginas marcadas e
   confirme. A cópia de até 100 páginas usa 150 DPI e substitui por preto os
   pixels marcados. Ela perde a camada de texto, vetores, anexos, formulários,
   links e assinaturas. A fila publica a cópia depois de verificar a estrutura
   e os pixels. Confira o arquivo final antes de compartilhá-lo.

**Inserir assinatura visual** pede uma área na página e abre o desenho ou a
seleção de imagem PNG/JPEG. A marca é uma anotação sem verificação
criptográfica. Use **Salvar como** para gravá-la e **Ctrl+Z** para desfazer.

Com o extra opcional `signing`, **Assinar digitalmente uma cópia** cria uma
assinatura invisível a partir de um arquivo local `.p12` ou `.pfx`. O comando
aceita PDFs íntegros, sem criptografia e sem assinaturas anteriores.
**Verificar assinaturas digitais** usa a revisão ativa da aba e pode receber
raízes X.509 locais `.pem`, `.crt`, `.cer` ou `.der`. A confiança depende
dessas raízes. O relatório separa integridade, criptografia e cobertura
do arquivo. A verificação offline usa as evidências de revogação disponíveis
no documento. O Old School PDF não consulta serviços de revogação ou carimbo de tempo.

## Organizar o espaço de leitura

O visual é o **Clássico 2000**, em **Exibir > Tema**. Arraste o título de um
painel para movê-lo. **Exibir > Painéis** controla a visibilidade e **Restaurar
organização padrão** recupera o arranjo inicial.

**Ferramentas > Preferências** configura ícones, atalhos, cache de páginas e
quantidade de operações simultâneas. O caminho do INI aparece em **Local e
privacidade**. **F1** abre o guia local na janela.

Arquivos de rede e pastas sob demanda precisam de uma cópia em uma unidade
local. A leitura aceita PDFs de até 512 MiB e 100 mil páginas. A busca lista até
mil ocorrências. O visualizador informa quando o tamanho de uma página exige
uma imagem de resolução reduzida.
