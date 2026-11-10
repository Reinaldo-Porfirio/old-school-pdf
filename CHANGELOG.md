# Alterações

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
