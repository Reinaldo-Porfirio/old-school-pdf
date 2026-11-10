# ADR 0005 · Segurança de cópias e assinaturas locais

**10/11/2026** · M5.

As ações de segurança leem a revisão ativa da aba e reutilizam a publicação
validada do M2. A origem e a revisão de trabalho ficam protegidas contra
substituição. PDFs com indicação de assinatura exigem ciência da invalidação
antes de uma exportação que reescreva o documento.

## Metadados e proteção

Remoção seletiva abrange a ficha padrão Info e o XMP do documento. São opções
independentes. Selecionar todos os campos de Info remove a ficha completa. A
saída é regravada sem atualizações incrementais e reaberta
para conferir os campos escolhidos. Em PDFs criptografados, alterações de
proteção ou metadados exigem autorização do proprietário. A proteção nova usa
AES-256 e senhas distintas para proprietário e abertura. O teste de saída
confere autenticação e bits de permissão. As permissões são interpretadas pelo
leitor que abre o PDF. O DocForge distingue modificação de conteúdo de
organização de páginas em revisões R3 ou posteriores e aplica as permissões
de modificação e anotação correspondentes em PDFs legados R2.
[Criptografia na API do PyMuPDF](https://pymupdf.readthedocs.io/en/latest/the-basics.html) ·
[ISO 32000-1, tabela 22](https://udp.adobe.io/document-services/docs/assets/35e4369068f86065372c18787171a17e/PDF_ISO_32000-1.pdf)

## Redação

O fluxo validado cria um PDF do zero com uma imagem RGB por página, a 150 DPI.
Os pixels marcados são substituídos por preto antes da criação das imagens. Objetos,
camadas ocultas, versões antigas, anexos e texto original ficam fora do arquivo
gerado. Isso implica perda de busca, vetores, assinaturas e interatividade na
cópia. As marcas são revisadas no visualizador e vinculadas à revisão atual.
A saída é auditada por extração de texto, inspeção da estrutura e comparação
dos pixels de cada área marcada. O limite é de 100 áreas, 100 páginas e
100 milhões de pixels no documento. A rasterização de páginas sem marcas
também evita transportar dados ocultos da origem. O T16 verificou texto
visível e invisível, camada opcional oculta, anexo, XMP, formulário, link,
ação de abertura e uma página recortada e girada.

## Assinaturas

A marca visual pode vir de um desenho ou de uma imagem e participa do histórico
normal da aba. Para assinatura criptográfica, a versão fixada é pyHanko 0.38.1
(MIT, Python 3.11 ou superior). O teste usa um arquivo PKCS#12 sintético e uma
raiz local, sem armazenamento de credenciais. A integração é opcional e exige
validação de integridade, assinatura, cobertura e confiança. A assinatura cria
um campo invisível e cobre o arquivo completo. A verificação separa revisões
posteriores e adulteração, usa somente raízes escolhidas e tem revogação
limitada às evidências locais. A assinatura exige PDF sem criptografia,
íntegro, sem assinaturas anteriores e com XMP legível quando presente.
[Distribuição oficial do pyHanko](https://pypi.org/project/pyHanko/0.38.1/) ·
[Guia de assinatura](https://docs.pyhanko.eu/en/latest/lib-guide/signing.html)

## Texto existente

O piloto extraiu caracteres e posições de três trechos em fontes diferentes
com `rawdict`. O recurso PDF da fonte incorporada continha um subconjunto
com codificação `Identity-H`. A página rasterizada equivalente não tinha
texto extraível. Inserir uma frase maior na caixa do texto original retornou
um déficit de 141,78 pt. A edição de texto existente segue indisponível.
Para chegar a uma edição fiel, ainda seria preciso tratar fontes incorporadas,
ligaduras, reposicionamento de linhas e texto convertido em vetores ou imagens.
[Extração por caractere](https://pymupdf.readthedocs.io/en/latest/app1.html) ·
[Inserção de texto](https://pymupdf.readthedocs.io/en/latest/recipes-text.html)
