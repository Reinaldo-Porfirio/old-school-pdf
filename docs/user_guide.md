# Guia do DocForge Ultimate

Abra o DocForge com `python -m docforge`. Pressione **Ctrl+O**, use
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

## Anotar e preencher

- Abra **Editar > Anotações** ou **Propriedades e ferramentas > Edição**.
  Arraste sobre texto para destacar ou sublinhar. Clique para inserir um
  comentário. Caixas de texto, carimbos, formas e imagens usam uma área arrastada.
  **Esc** encerra a ferramenta de posicionamento.
- Selecione a anotação na página ou na lista do painel Edição. As opções de
  mover, editar texto e excluir dependem do tipo e das permissões do objeto.
- **Documento > Preencher formulário** permite editar campos AcroForm da página
  atual. Campos com scripts ou formato incompatível permanecem em leitura passiva.
- PDFs com indicação de assinatura digital pedem confirmação antes da edição ou
  exportação. A janela informa o risco de invalidar a assinatura na cópia.

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
- **Otimizar PDF** compacta a estrutura. Marque a redução de imagens se aceitar
  recompressão com perda. O relatório compara os tamanhos e a cópia é publicada
  quando houver redução.
- **Processar lote** também permite dividir PDFs em partes consecutivas e
  mesclar uma lista ordenada. O lote lê os arquivos salvos no disco. Use
  **Salvar como** para processar uma revisão que ainda esteja na aba.
- O lote grava cada resultado em uma pasta nova. A fila aceita cancelamento por
  tarefa ou por lote. O relatório permite abrir o PDF gerado, copiar os detalhes
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
no documento. O DocForge não consulta serviços de revogação ou carimbo de tempo.

## Organizar o espaço de leitura

**Exibir > Tema** alterna Classic Light e Graphite Pro. Arraste o título de um
painel para movê-lo. **Exibir > Painéis** controla a visibilidade e **Restaurar
organização padrão** recupera o arranjo inicial.

**Ferramentas > Preferências** configura ícones, atalhos, cache de páginas e
quantidade de operações simultâneas. O caminho do INI aparece em **Local e
privacidade**. **F1** abre o guia local na janela.

Arquivos de rede e pastas sob demanda precisam de uma cópia em uma unidade
local. A leitura aceita PDFs de até 512 MiB e 100 mil páginas. A busca lista até
mil ocorrências. O visualizador informa quando o tamanho de uma página exige
uma imagem de resolução reduzida.
