# ADR 0004 · OCR, conversão e lotes locais

**10/11/2026** · M4 · Aceita.

## OCR opt-in

O adaptador chama Tesseract pela interface `Pixmap.pdfocr_tobytes` do PyMuPDF
2.1/MuPDF 1.28.6. A pasta de modelos precisa ser selecionada e validada no
diálogo **Configurar OCR local**. A prova é o reconhecimento de uma imagem
sintética no processo do PDF para cada idioma detectado. O INI guarda somente
a pasta e os idiomas validados. A inicialização e o diagnóstico consultam a
presença local dos modelos sem iniciar o motor.

Os modelos de referência de QA foram `por` e `eng` de tessdata_fast 4.1.0, sob
Apache-2.0. O aplicativo aceita modelos locais compatíveis e as combinações
português, inglês e português com inglês. O wheel permanece com as dependências
de M3. A interface usa a integração existente do MuPDF e o usuário fornece os
arquivos de idioma. [Instalação e OCR do PyMuPDF](https://pymupdf.readthedocs.io/en/latest/installation.html) ·
[Modelos Tesseract](https://tesseract-ocr.github.io/tessdoc/Data-Files) ·
[Licença tessdata_fast](https://github.com/tesseract-ocr/tessdata_fast/blob/4.1.0/LICENSE)

O OCR rasteriza somente as páginas escolhidas que ainda não têm texto. A
imagem do PDF de OCR temporário é removida e a camada invisível é combinada
com a página original. A rotação e a região visível entram no cálculo da
posição. O PDF final é reaberto e a camada de cada página processada é
conferida. O fluxo preserva a inclinação visual do original. A qualidade do
reconhecimento depende do idioma, DPI e condição da digitalização.

## Conversões e otimização

Exportação de páginas para PNG e JPEG e criação de PDF com PNG, JPEG e TIFF,
incluindo TIFF com múltiplas imagens. Conversão em texto simples UTF-8, com
marcação de páginas. Extração de imagens por objeto incorporado referenciado.
Imagens inline sem referência própria ficam fora desse fluxo. O otimizador
recomprime a estrutura PDF e publica uma cópia se o tamanho diminuir. A opção
de recomprimir imagens permite perda de qualidade. O motor usa 150 DPI como
referência e reduz em etapas de 2× quando o tamanho e o uso da imagem permitem.
[API Document do PyMuPDF](https://pymupdf.readthedocs.io/en/latest/document.html)

## Processamento e integridade

- A fila aceita até 100 entradas. Mesclagem e imagens em PDF usam a lista
  inteira como uma tarefa. As demais operações registram uma tarefa por arquivo.
- O estágio de cada entrada fica na pasta escolhida. Arquivos PDF são
  reabertos e verificados. Depois da validação, a pasta é publicada com um
  nome exclusivo. Colisões ganham um sufixo numérico, preservando o destino
  existente. Cancelar uma entrada interrompe seu processo e descarta o estágio.
- A interface recebe progresso por mensagens locais. O prazo sem progresso é
  120 segundos por entrada. O relatório permite abrir PDFs, copiar o resultado
  e repetir entradas com falha ou canceladas. A fila fica na sessão da janela.
- Operações M4 partem de arquivos salvos, aceitam PDFs sem criptografia e
  exigem ciência explícita para modificar PDFs com indicação de assinatura.
  Imagens importadas têm limite de 64 MiB por arquivo e rasterizações de
  26 milhões de pixels. Uma entrada pode publicar até 2.000 arquivos.

## Integrações externas opcionais

O Windows de teste não tinha OCRmyPDF nem LibreOffice disponíveis. A conversão
Office permanece identificada como pendente de validação. A liberação exige
prova de fidelidade, isolamento de perfil e comportamento offline. O motor
Tesseract integrado cobre o reconhecimento validado do M4.
[Instalação oficial do OCRmyPDF](https://ocrmypdf.readthedocs.io/en/latest/installation.html) ·
[LibreOffice](https://www.libreoffice.org/download/)
