# ADR 0002 · Visualizador de PDFs

Aceito em 09/11/2026.

## Motor e licença

Fixamos PyMuPDF 2.1 pela opção GNU AGPLv3. A versão traz MuPDF 1.28.6 e
carregamento sob demanda dos componentes de layout. A série 2.x incorpora
a correção do estouro em `JM_set_annot_callout_line`. A versão 2.1 tem wheel
Windows x64 `cp311-abi3` e declara Python >=3.11. A execução local do DocForge
foi verificada no Python 3.13.15.
[PyPI](https://pypi.org/project/pymupdf/2.1/) ·
[Notas da versão](https://pymupdf.readthedocs.io/en/latest/changes.html) ·
[Licença](https://pymupdf.readthedocs.io/en/latest/about.html#license-and-copyright)

As dependências transitivas oficiais permanecem no lock. Os wheels 2.1 de
`pymupdf-layout` e `pymupdf4llm` contêm apenas metadados de compatibilidade.
O processo usa `pymupdf.use_layout(False)` para trabalhar com a camada de texto
e com o rasterizador padrão. A verificação de importação confirmou a ausência
de `onnxruntime` nos módulos carregados pelo leitor.
[Documentação do layout](https://pymupdf.readthedocs.io/en/latest/rag.html) ·
[Inventário instalado](../evidence/m1-dependencies.json)

## Processos e limites

PyMuPDF recomenda processos para concorrência. Cada aba PDF mantém um leitor
próprio, iniciado pelo interpretador do aplicativo. QProcess transfere pedidos
por entrada padrão e recebe metadados JSON e raster RGB por saída padrão.
O agendador usa duas operações simultâneas por padrão e aceita de uma a quatro
nas preferências. Leitores de abas abertas podem permanecer ociosos.
[Orientação de concorrência do PyMuPDF](https://pymupdf.readthedocs.io/en/latest/recipes-multiprocessing.html)

Cada pedido tem prazo de 20 segundos. O processo de uma aba é encerrado em
caso de falha fatal, prazo excedido ou cancelamento de abertura. A busca envia
uma página por vez e descarta respostas de consultas substituídas ou canceladas.
O isolamento mantém a interface e as outras abas disponíveis em caso de falha
do leitor. O processo usa as permissões da conta que executa o DocForge.

O cache LRU de rasters é compartilhado pela janela e vai de 16 a 256 MiB,
com 64 MiB por padrão. Só as miniaturas visíveis são solicitadas. A aba inativa
libera a imagem exibida e pode recuperá-la do cache ao voltar. Pedidos de
zoom obsoletos perdem prioridade e suas imagens ficam fora da tela.

| Limite | Valor |
|---|---:|
| Arquivo de entrada | 512 MiB |
| Páginas por documento | 100.000 |
| Dimensão lógica de página | 25.000 pontos PDF por eixo |
| Raster de uma resposta | Aproximadamente 8 milhões de pixels |
| Consulta e ocorrências de busca | 160 caracteres e 1.000 resultados |
| Texto copiado por operação | 128.000 caracteres |

No Windows, caminhos UNC, unidades de rede e componentes com pontos de
reanálise ou atributos de disponibilidade sob demanda pedem uma cópia local.
A identificação PDF usa extensão e cabeçalho. O leitor usa erros localizados
e mantém avisos brutos do motor fora da interface e do registro de tarefas.

## Interação

A tela mostra uma página por vez. O zoom tenta preservar o ponto central
visível e a rotação é uma transformação da visualização. A busca normaliza
espaços, maiúsculas e minúsculas em Unicode. Os realces usam retângulos da
linha ou das palavras que compõem a ocorrência. A cópia trabalha com a página
ou com um retângulo selecionado e segue a permissão do documento.

Um atalho configurado no M0 tem precedência sobre um novo atalho padrão do
visualizador. Em caso de conflito na migração, o novo comando fica disponível
pelo menu e recebe um atalho editável nas preferências.
