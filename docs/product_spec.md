# DocForge Ultimate — Especificação de Produto e Engenharia (v1.0)

**Estado:** especificação proposta, nenhum recurso declarado como implementado.  
**Data:** 03/11/2026  
**Produto:** suíte desktop para PDF e documentos, gratuita, sem assinatura, sem login e local-first.  
**Público-alvo:** estudantes, docentes, famílias, profissionais de escritório, autônomos e pequenas empresas.  
**Plataforma prioritária:** Windows 11 x64; Windows 10 x64 como compatibilidade a verificar; Ubuntu Linux na etapa posterior.  
**Idioma inicial:** português brasileiro; inglês preparado via internacionalização.  
**Distribuição pretendida:** código-fonte público e instalador gratuito, sem marca-d'água, limitações artificiais ou telemetria obrigatória.

> Este documento é uma especificação de construção e testes, não uma alegação de que o programa foi desenvolvido. O Claude Code deverá confirmar a compatibilidade técnica e as licenças das versões efetivamente utilizadas antes de distribuir binários.

---

## 1. Missão e princípios inegociáveis

**Missão:** dar ao usuário uma oficina de documentos completa, acessível e robusta, com o poder das suítes clássicas e sem assinaturas.

1. **Software completo:** todas as funcionalidades implementadas são gratuitas; nenhuma tela de upgrade, marca-d'água, limitação de número de arquivos ou de exportações.
2. **Offline de verdade:** abrir, editar, pesquisar, converter localmente e exportar PDFs não exige conexão, autenticação nem serviços terceiros.
3. **Interface desktop rica:** menus tradicionais, barras de ferramentas, painéis redimensionáveis, ícones explícitos, atalhos, menus de contexto e barra de status. Não sacrificar recursos em nome de minimalismo.
4. **Confiabilidade antes de quantidade:** recursos parcialmente funcionais não são anunciados como concluídos.
5. **Segurança de arquivos:** a operação padrão nunca sobrescreve o arquivo original; salvar em novo caminho, salvamento atômico e recuperação quando possível.
6. **Privacidade:** arquivos locais ficam locais. Não enviar nomes, conteúdo, metadados ou telemetria; exceções apenas com ação expressa do usuário em recursos opcionais futuros.
7. **Transparência:** mensagens claras sobre limitações, arquivos criptografados, assinaturas, OCR imperfeito, fontes não disponíveis e dependências opcionais.
8. **Acessibilidade:** navegação por teclado, alto contraste, suporte a escalonamento DPI, estados de foco visíveis, descrições acessíveis e atalhos configuráveis.

### 1.1 Pessoas e jornadas

- **Estudante:** unir apostilas, numerar páginas, destacar, comentar e extrair trechos.
- **Professor:** reorganizar material, inserir anotações e exportar exercícios.
- **Profissional:** preencher formulários, digitalizar, aplicar OCR e preparar documentos para envio.
- **Família:** extrair páginas de contratos, comprimir arquivos, ocultar dados sensíveis e organizar comprovantes.
- **Usuário avançado:** processamento em lote, configurações detalhadas, automação via CLI futura e inspeção de propriedades do PDF.

### 1.2 Indicadores de qualidade (não afirmações de desempenho)

- Abertura, alteração e salvamento de um PDF de teste sem corrupção.
- UI não bloqueia perceptivelmente durante processos pesados; barra de progresso, cancelamento e registro de erro.
- Zero perda silenciosa de conteúdo nas operações aceitas pelos testes.
- Funções destrutivas exigem confirmação; não devem modificar os originais sem solicitação explícita.
- Toda funcionalidade do menu possui comportamento real ou está claramente marcada como futura e desabilitada.
- Operações de OCR e exportação devem produzir arquivos que possam ser reabertos e verificados.

---

## 2. Escopo funcional priorizado

**Legenda:** P0 = primeira versão utilizável (MVP); P1 = release seguinte; P2 = avançado; R = pesquisa/risco técnico antes de anunciar.

| Módulo | Recurso | Prioridade | Critério de aceitação |
|---|---|---|---|
| Visualizador | Abrir PDFs, múltiplas abas, senha para PDF protegido | P0 | Abre documento válido, informa erro ao falhar, não registra senha |
| Visualizador | Miniaturas, zoom, ajuste à página/largura, rotação de visualização | P0 | Navegação e escalonamento mantêm proporções e estado |
| Visualizador | Localização por página, busca textual, copiar texto | P0 | Navega até ocorrência em PDF com camada de texto |
| Visualizador | Marcadores/índice, propriedades e metadados | P1 | Exibe itens disponíveis e informa campos ausentes |
| Organizador | Mesclar, dividir, extrair e excluir páginas | P0 | Saída preserva quantidade e ordenação escolhidas |
| Organizador | Reordenar e girar páginas, arrastar miniaturas | P0 | Alterações aparecem na prévia e persistem na saída |
| Organizador | Inserir páginas PDF/imagem, páginas em branco | P1 | Dimensões e orientação configuráveis |
| Editor | Marca-texto, sublinhado, comentário, texto sobreposto | P1 | Anotações persistem e não substituem conteúdo original indevidamente |
| Editor | Caixas de texto, figuras, carimbo, imagens e formas | P1 | Posicionamento correto após zoom, rotação e exportação |
| Editor | Seleção de objeto, movimentação, exclusão, desfazer/refazer | P1 | Ações suportadas restauram o estado esperado |
| Editor | Preencher formulários AcroForm compatíveis | P1 | Campos editados persistem e podem ser reabertos |
| Editor | Edição de texto **existente** com preservação de layout | R/P2 | Exigir protótipo e testes; não prometer equivalência ao Acrobat |
| OCR | Converter PDF digitalizado em PDF pesquisável (pt-BR/inglês) | P1 | Texto extraível de amostras digitalizadas com tolerâncias documentadas |
| OCR | Processar páginas selecionadas e lotes; deskew básico | P2 | Funciona sem travar UI, registra falhas por arquivo |
| Conversor | Imagens JPG/PNG/TIFF → PDF, PDF → imagem | P1 | Mantém ordem, qualidade e proporção configuradas |
| Conversor | PDF → TXT e imagens incorporadas | P1 | Extrai dados disponíveis e comunica perda de formatação |
| Conversor | DOCX/ODT/PPTX → PDF via LibreOffice local opcional | P2 | Declara instalação externa e testa layout básico |
| Conversor | PDF → DOCX de alta fidelidade | R/P2 | Não anunciar antes de validador de fidelidade e solução adequada |
| Otimizador | Compressão simples, redução de imagens, limpeza estrutural | P1 | Compara tamanho e qualidade; não promete sempre reduzir |
| Segurança | Remover metadados selecionados | P1 | Metadados removidos não reaparecem na leitura do arquivo salvo |
| Segurança | Redação **irreversível** de conteúdo sensível | P2, alta exigência | Verificações por extração de texto, rasterização e inspeção estrutural |
| Segurança | Proteger PDF com senha, permissões | P2 | Reabertura e validação de permissões; alertas sobre limites do formato |
| Assinaturas | Assinatura visual (imagem/desenho), explicitamente NÃO criptográfica | P1 | Aparência exportada; UI explica que não prova autoria criptograficamente |
| Assinaturas | Assinatura digital com certificado e validação (pyHanko) | P2 | Verificação real, política de assinatura e alertas de invalidação |
| Lotes | Filas com opções de mesclar, separar, otimizar, converter | P1 | Cancelar, retomar quando possível, log por tarefa e relatório final |
| Aplicativo | Preferências, temas, atalhos, idioma, atualização manual | P0/P1 | Persistência local; sem verificação compulsória por rede |
| Aplicativo | Instalador Windows, documentação e ajuda offline | P1 | Instala e desinstala com sucesso em máquina limpa de teste |
| Automação | CLI para operações básicas headless | P2 | Usa os mesmos serviços do núcleo, não duplica lógica |

### 2.1 Fora do escopo inicial

- Colaboração multiusuário em tempo real ou SaaS.
- Sincronização na nuvem, armazenamento online, conta de usuário.
- Editor nativo completo de DOCX/XLSX/PPTX.
- Reflow universal e sem perdas de texto já existente em qualquer PDF.
- Promessa de suportar todos os arquivos danificados, assinados, com JavaScript ou recursos multimídia.
- Desbloqueio de PDFs sem autorização ou quebra de criptografia.
- Alegar equivalência jurídica entre assinatura desenhada e assinatura digital validada.

---

## 3. Interface — Classic Pro, não minimalista

**Direção visual:** software desktop profissional da era de ferramentas completas, com legibilidade e acessibilidade atuais; referência de densidade de informação: gerenciadores de arquivos clássicos, suítes Office tradicionais e editores PDF avançados. Evitar clonagem visual de marcas existentes.

### 3.1 Janela principal

```text
┌──────────────────────────────────────────────────────────────────────────────────────┐
│ DocForge Ultimate — Contrato.pdf *                                       _ □ X      │
├──────────────────────────────────────────────────────────────────────────────────────┤
│ Arquivo  Editar  Exibir  Documento  Ferramentas  OCR  Segurança  Janela  Ajuda       │
├──────────────────────────────────────────────────────────────────────────────────────┤
│ [Abrir] [Salvar como] [Imprimir] | [Desfazer] [Refazer] | [Mesclar] [Dividir] [OCR] │
│ [Selecionar] [Texto] [Destacar] [Comentário] [Carimbo] | Zoom [-] [125%] [+]        │
├──────────────────────────────────────────────────────────────────────────────────────┤
│ [Contrato.pdf ×] [Apostila.pdf ×] [Trabalho.pdf ×]                                    │
├─────────────────────┬────────────────────────────────────┬───────────────────────────┤
│ PÁGINAS / ÍNDICE     │            DOCUMENTO               │ PROPRIEDADES / FERRAMENTAS  │
│ [miniatura 1]       │                                    │ Página: 2                  │
│ [miniatura 2]       │       ┌───────────────────┐        │ Tamanho: A4                │
│ [miniatura 3]       │       │                   │        │ Rotação: 0°                │
│ [miniatura 4]       │       │   PDF renderizado  │        │ Anotações / selecionado     │
│                     │       │                   │        │ Cores, fontes e coordenadas│
│ [filtro]            │       └───────────────────┘        │ [Aplicar] [Limpar]         │
├─────────────────────┴────────────────────────────────────┴───────────────────────────┤
│ TAREFAS | Progresso  68%  [Cancelar]   Avisos: 0   Resultado: --                    │
├──────────────────────────────────────────────────────────────────────────────────────┤
│ Página 2/24  |  125%  | A4 | Não salvo  | OCR: não  |  Local / Offline              │
└──────────────────────────────────────────────────────────────────────────────────────┘
```

### 3.2 Regras de UI

- **QMainWindow + QDockWidget + QTabWidget**, com painéis redimensionáveis e disposição lembrada.
- Dois estilos: **Classic Light** (claro, barras azuis) e **Graphite Pro** (escuro, alto contraste). Ícones nítidos e coloridos onde agregam significado.
- Menus completos sempre acessíveis; barras de ferramentas configuráveis, opção de texto sob ícones e atalhos visíveis nos menus.
- Painéis: miniaturas/índice à esquerda, propriedades/formatos à direita, fila de tarefas na parte inferior.
- Múltiplas abas e documentos, área central principal com rolagem e zoom.
- Faixa de tarefas específica por modo: **Início**, **Editar**, **Páginas**, **OCR**, **Converter**, **Proteção**, **Lotes**. Preferir barra de ferramentas tradicional sobre ribbon complexa no MVP.
- Pesquisa global por comando em `Ctrl+Shift+P` opcional no P1, sem remover menus.
- Mensagens de conclusão, erro e advertência compreensíveis; não usar apenas cor para distinguir estado.
- `Ctrl+O`, `Ctrl+Shift+S`, `Ctrl+F`, `Ctrl+Z`, `Ctrl+Y`/`Ctrl+Shift+Z`, `Ctrl+P` quando implementados; `Delete` só com seleção e confirmação quando destrutivo.
- Arrastar e soltar arquivos na janela; arrastar miniaturas para reordenar.
- Interface 100% português-BR no MVP, arquitetura preparada para `QTranslator`.
- Recursos indisponíveis devem ser desabilitados com explicação, não criar botões decorativos que nada fazem.

### 3.3 Fluxos essenciais

**Fluxo A — Unir apostilas**
1. Abrir `Arquivo > Mesclar PDFs`.
2. Arrastar múltiplos PDFs, reorganizar a lista, visualizar quantidade de páginas.
3. Escolher caminho de saída **novo**.
4. Executar em segundo plano, verificar resultado e abrir PDF gerado.

**Fluxo B — Destacar e comentar**
1. Abrir PDF, encontrar trecho por busca.
2. Selecionar texto, clicar em `Destacar`; inserir anotação e opcionalmente comentário.
3. Ver estado `Não salvo`, desfazer, refazer, salvar como.
4. Reabrir e conferir anotação no mesmo local.

**Fluxo C — Digitalizar para texto pesquisável**
1. Abrir PDF escaneado e clicar em `Reconhecer texto`.
2. Escolher idiomas pt-BR e/ou inglês; pré-visualizar páginas e modo de saída.
3. Executar tarefa cancelável, exportar outro arquivo e testar busca.
4. Em caso de falha, preservar original e explicar dependência ausente ou erro por página.

---

## 4. Arquitetura proposta

### 4.1 Direção tecnológica

| Camada | Ferramenta | Justificativa |
|---|---|---|
| Interface | Python 3.12+ e PySide6 (Qt Widgets) | Desktop nativo, dock widgets, menus e internacionalização |
| Motor PDF principal | PyMuPDF (MuPDF) | Renderização, textos, anotações, manipulação e redação PDF |
| Integridade/estrutura PDF | pikepdf (QPDF), conforme necessidade | Estrutura PDF, metadados e tarefas de baixo nível |
| OCR local | Tesseract + OCRmyPDF | Produção de camada pesquisável, sem IA paga |
| Conversão Office opcional | LibreOffice headless | Ferramenta externa sem servidor, dependência opcional |
| Assinatura digital futura | pyHanko | Assinaturas/verificação com certificados |
| Configurações e histórico de tarefas | SQLite + TOML ou QSettings | Estado local, restauração de preferências e diagnósticos |
| Concorrência | QThreadPool/QThread para coordenação; processos para tarefas isoladas | Manter UI responsiva e isolar trabalho pesado |
| Testes | pytest, pytest-qt e testes de arquivos reais gerados | Cobertura unitária, UI, regressão e integração |
| Empacotamento | PyInstaller + Inno Setup, sujeito à validação | Distribuição Windows e licença dos componentes |

**Nota decisiva sobre licença:** PyMuPDF é disponibilizado sob **AGPLv3 ou licença comercial**. Para que o DocForge permaneça grátis e sem licença comercial, assumir desde o início que o projeto será publicado como software livre compatível com AGPL, com código-fonte correspondente e avisos de licença. PySide6 tem modalidades LGPL/GPL/comercial; pikepdf e OCRmyPDF usam MPL-2.0; Tesseract usa Apache-2.0. Validar módulos, versões, artefatos distribuídos e licenças de terceiros no processo de empacotamento. Consulte fontes ao final. **Não interpretar a licença sem revisão jurídica caso haja redistribuição formal.**

### 4.2 Componentes e fluxo

```text
+--------------------------+
| Qt Widgets / GUI         |
| menus, abas, canvas, UI  |
+-------------+------------+
              |
              v
+--------------------------+
| Application Services     |
| comandos, eventos, filas |
| undo/redo, orchestration |
+-------+------------+-----+
        |            |
        v            v
+---------------+  +-----------------------+
| PDF Domain    |  | Background Job Engine |
| Document      |  | subprocessos e logs   |
| Page, EditOp  |  +------------+----------+
| ExportSpec    |               |
+-------+-------+               v
        |               +-------------------+
        v               | OCR / Conversão   |
+----------------------+| Tesseract, LO     |
| Adapter PDF          || opcional          |
| PyMuPDF / pikepdf    |+-------------------+
+----------+-----------+
           |
           v
+--------------------------+
| Filesystem + SQLite      |
| temporários, backup,     |
| preferências e logs      |
+--------------------------+
```

### 4.3 Contratos de serviço (interfaces, não APIs definitivas)

- `DocumentService.open(path, password_callback?) -> DocumentSession`
- `DocumentService.inspect(session) -> DocumentMetadata`
- `RenderService.render_page(session, page_index, zoom, rotation) -> ImageBuffer`
- `SearchService.find(session, text, options) -> SearchHits`
- `PageService.merge(inputs, output, options) -> Result`
- `PageService.split(input, ranges, output_dir) -> Result`
- `PageService.reorder(session, page_ids) -> EditCommand`
- `AnnotationService.add(session, page_id, annotation) -> EditCommand`
- `ExportService.export(session, output, settings) -> Result`
- `OCRService.process(input, output, languages, page_ranges, progress, cancel) -> JobResult`
- `JobService.submit(task) -> TaskId`, `cancel(task_id)`, `status(task_id)`
- `CapabilitiesService.check() -> CapabilitiesReport` para detectar Tesseract/LibreOffice/certificados.

**Separação obrigatória:** widgets nunca devem chamar `pymupdf` diretamente. Todas as operações passam por serviços, para possibilitar testes e troca de implementação.

### 4.4 Estado documental e salvamento

- Cada aba possui `DocumentSession` com `source_path`, `working_copy`, `dirty`, `page_map`, `zoom`, `selection`, `undo_stack` e estado de assinatura.
- Original preservado por padrão. Editar apenas em memória ou cópia de trabalho temporária.
- `Salvar como` grava primeiro em arquivo temporário na mesma pasta de destino, valida o resultado e usa troca atômica quando permitida pelo sistema.
- Em colisão de nomes ou possível substituição, solicitar confirmação e oferecer backup.
- `Undo/Redo` comandado por objetos de domínio. Alterações complexas podem requerer snapshot de sessão; impor limites de memória.
- Abrir PDF com assinatura: detectar assinatura quando possível e exibir alerta antes de qualquer edição, pois alterações podem invalidá-la.
- Não assumir que assinaturas digitais sobrevivem à regravação; política conservadora de edição e exportação.
- Exibir aviso de modificações não salvas ao fechar aba/programa.

### 4.5 Processamento assíncrono

- Renderização de páginas sob demanda, cache LRU com limite configurável, cancelamento de render obsoleto.
- OCR, compactação, lote e conversão Office em processos isolados com timeout e logs.
- UI atualizada por sinais/eventos, nunca atualizada diretamente de uma thread secundária.
- Máximo configurável de workers e limitação de recursos para PDFs gigantes.
- Registros por tarefa: identificador, tipo, início/fim, progresso, arquivos de entrada/saída, status e erro sanitizado.
- Ao cancelar uma tarefa, não publicar resultado parcial como conclusão; limpar temporários sem apagar originais.

### 4.6 Estrutura de pastas sugerida

```text
docforge/
  pyproject.toml
  README.md
  LICENSE
  THIRD_PARTY_NOTICES.md
  docs/
    product_spec.md
    architecture.md
    test_plan.md
    user_guide.md
    decisions/
  src/docforge/
    __init__.py
    __main__.py
    app.py
    domain/
      models.py
      commands.py
      errors.py
    application/
      document_service.py
      render_service.py
      page_service.py
      annotation_service.py
      search_service.py
      export_service.py
      job_service.py
      capability_service.py
    infrastructure/
      pdf/
        pymupdf_backend.py
        pikepdf_backend.py
      ocr/
        ocrmypdf_adapter.py
      conversion/
        libreoffice_adapter.py
      persistence/
        settings_repository.py
        task_repository.py
      filesystem/
        safe_write.py
    ui/
      main_window.py
      pdf_canvas.py
      thumbnails_dock.py
      properties_dock.py
      jobs_dock.py
      dialogs/
      widgets/
      themes/
      icons/
      i18n/
  tests/
    unit/
    integration/
    gui/
    security/
    performance/
    fixtures/
  scripts/
  packaging/
    windows/
    linux/
```

**Mantenha simplicidade:** diretórios vazios não devem ser criados só para parecer arquitetura. Criar módulos conforme forem necessários, sem microserviços nem frontend web desnecessários.

---

## 5. Licença, direitos e dependências

1. **Decisão proposta:** DocForge publicado sob `AGPL-3.0-or-later` (revisar compatibilidade exata com dependências e outras licenças antes da publicação). Documentar PyMuPDF e avisos necessários. O objetivo é permitir uso gratuito, revisão do código e distribuição conforme licença.
2. Nenhuma dependência deve exigir aquisição de licença comercial para a distribuição planejada. Recursos incompatíveis devem ser substituídos, opcionalizados ou adiados.
3. Não usar bibliotecas de origem desconhecida nem copiar ícones/assets de software proprietário.
4. Incluir `LICENSE`, `THIRD_PARTY_NOTICES.md`, fontes dos ícones, versões e licenças dos binários empacotados.
5. Não incluir motores de OCR, modelos ou codecs sem verificar licenças e direitos de redistribuição.
6. Conversão LibreOffice executada como programa externo opcional, com verificação de versão e executável; documentação explica possíveis diferenças de formatação.
7. Não sugerir que dados sensíveis foram destruídos porque um retângulo preto foi desenhado por cima.
8. Antes de divulgação pública, pesquisar disponibilidade do nome e possíveis marcas registradas "DocForge".

Fontes técnicas e de licença a conferir durante a implementação:

- PyMuPDF: https://pymupdf.io/licensing e https://pymupdf.readthedocs.io/en/latest/
- PySide6/Qt: https://doc.qt.io/qt-6/licensing.html e https://pypi.org/project/PySide6/
- pikepdf: https://github.com/pikepdf/pikepdf
- OCRmyPDF: https://ocrmypdf.readthedocs.io/en/stable/installation.html e https://github.com/ocrmypdf/OCRmyPDF
- Tesseract: https://tesseract-ocr.github.io/tessdoc/Installation.html
- pyHanko: https://docs.pyhanko.eu/en/latest/

---

## 6. Segurança, privacidade e arquivos hostis

### 6.1 Modelo de ameaça

Entrada pode conter PDFs malformados, com fontes defeituosas, objetos enormes, páginas gigantes, links maliciosos, anexos, conteúdo ativo, dados sensíveis ou assinaturas digitais. A interface também pode lidar com paths estranhos, permissões negadas, falta de espaço e queda de energia durante salvamento.

### 6.2 Requisitos mínimos

- Não executar JavaScript de PDFs, macros ou anexos. Links externos apenas após clique do usuário e confirmação em contextos suspeitos.
- Não executar binários sugeridos por conteúdo do documento.
- Validar extensões e assinaturas de arquivo; nunca confiar apenas no nome.
- Limitar tamanho e tempo de tarefas conforme configurações; mostrar erro claro para limites excedidos.
- Não registrar texto de documentos, senhas, tokens ou caminhos completos em logs compartilháveis por padrão; oferecer log sanitizado.
- Usar diretórios temporários locais, com permissões adequadas, e remoção segura das cópias ao finalizar quando possível (sem alegar eliminação forense).
- Não enviar documentos para APIs web em nenhuma funcionalidade padrão.
- Senhas de PDFs nunca são persistidas; solicitar novamente quando necessário.
- Não remover páginas, anexos ou metadados de documentos assinados sem alertar sobre invalidação.
- **Redação real:** implementar usando mecanismo que remove efetivamente conteúdo, não sobreposição visual. Auditar camada de texto, render e objetos PDF pertinentes. Se não houver prova suficiente, manter recurso indisponível.
- Evitar injeção em chamadas de processos externos: usar lista de argumentos, sem `shell=True`, e validar paths.

---

## 7. Estratégia de testes

### 7.1 Pirâmide de testes

**Unitários:** parsing de intervalos de páginas, validação de caminhos, nomes de arquivos, composição de comandos, histórico de desfazer, políticas de confirmação, formatação de progresso e detecção de capabilities.

**Integração com PDFs:** gerar e manter fixtures: PDF de 1 página; PDF de 100 páginas; paisagem; tamanhos mistos; caracteres acentuados; anexos; imagens; páginas giradas; PDF sem texto; PDF criptografado com senha conhecida; formulário; assinatura sintética quando viável; PDFs malformados; arquivo muito grande.

**Testes de UI:** abrir/fechar abas, zoom, busca, rotação, menu, atalhos, arrastar/reordenar miniaturas, cancelamento, layout salvo, DPI alto, português-BR, estado `dirty` e diálogos de confirmação.

**E2E:** iniciar programa em máquina/ambiente limpo, carregar arquivo fixture, mesclar, exportar, reabrir, verificar página e texto; OCR; saída e logs.

**Regressão visual:** snapshots de páginas renderizadas e comparação com tolerância explícita; não comparar pixel exato em todas as plataformas sem considerar fontes e antialiasing.

**Segurança:** URLs maliciosas, PDF com scripts, paths com espaços e caracteres especiais, PDF criptografado, arquivo truncado, recursos massivos, senha não logada, export sem sobrescrever original; testes específicos de redação real.

**Performance:** medir em hardware conhecido, por exemplo PDFs de 10, 100 e 1000 páginas, consumo de memória, tempo de abertura, navegação, OCR e batch. Estabelecer limites **após** coletar baseline, não inventar promessa de desempenho.

### 7.2 Casos de teste prioritários (ID e saída esperada)

| ID | Cenário | Resultado mínimo |
|---|---|---|
| T01 | Abrir PDF válido | Primeira página aparece, contador certo |
| T02 | Abrir PDF criptografado sem senha | Solicita senha, não trava |
| T03 | Abrir PDF corrompido | Erro inteligível, UI continua aberta |
| T04 | Zoom 50% → 200% | Página mantém proporção e foco coerente |
| T05 | Buscar frase em PDF textual | Encontra ocorrências e permite navegar |
| T06 | Mesclar dois PDFs (3 e 5 páginas) | Novo PDF tem 8 páginas na ordem esperada |
| T07 | Dividir páginas 2–4 de PDF com 8 páginas | Novo PDF tem exatamente 3 páginas |
| T08 | Reordenar e girar páginas | Saída reabre com sequência/orientação escolhidas |
| T09 | Cancelar exportação em andamento | Nenhum original alterado; temporários tratados |
| T10 | Falha de escrita / sem permissão | Erro exibido, origem intacta |
| T11 | Fechar aba com modificações | Pergunta se deseja salvar, descartar ou cancelar |
| T12 | Edição de anotação + salvar como + reabrir | Anotação no local esperado |
| T13 | OCR de digitalização pt-BR | Saída pesquisável, texto esperado detectado |
| T14 | OCR com Tesseract ausente | Recurso desabilitado com instruções úteis |
| T15 | PDF assinado editado | Mostra alerta de potencial invalidação |
| T16 | Redação com texto sensível (quando habilitada) | Texto não recuperável nos testes definidos |
| T17 | Assinatura visual | UI informa que não é assinatura digital |
| T18 | Abrir dez abas e executar lote | UI responsiva e logs de tarefas íntegros |
| T19 | Reiniciar aplicativo | Tema, painéis e últimas preferências preservados |
| T20 | Empacotar Windows e instalar em ambiente limpo | Executável abre sem Python global e operações P0 funcionam |
| T21 | Exemplo com Unicode, emoji e caminhos longos | Sem crash ou corrupção silenciosa |
| T22 | Exportar para caminho já existente | Confirmação e prevenção de sobrescrita acidental |

### 7.3 Critérios para considerar um marco concluído

- Código executável localmente, com instruções reproduzíveis.
- Testes do marco passando; resultados reais anexados em `docs/test_report.md`.
- Teste manual de fluxo completo realizado; declarar explicitamente passos que dependem do usuário ou de ambiente Windows e não foram testados.
- Nenhuma função anunciada deve ser um mock ou botão inerte.
- Registros de erro e tratamento dos casos de falha relevantes.
- O código não executa uploads ou requisições externas inesperadas.
- Ausência de regressão conhecida nas funcionalidades dos marcos anteriores.

---

## 8. Roadmap e critérios de entrega

### M0 — Alicerce técnico

- [ ] Inicializar repositório, ambiente virtual, `pyproject.toml`, ferramentas de qualidade, licença e avisos.
- [ ] Criar janela Qt real com menus, dock panels, abas, preferências, tema clássico claro/escuro, atalhos.
- [ ] Definir contratos de serviço, `DocumentSession`, errors, capability checker e serviços fake **apenas para testes internos**.
- [ ] Configurar CI para testes headless de lógica e UI, sem anunciar funcionalidades não implementadas.
- [ ] Primeiro projeto demonstrável e arquitetura documentada.

**Aceitação M0:** inicia com `python -m docforge`; layout persiste; sem erros no console; testes de janela e configurações passam.

### M1 — Visualizador real (primeiro protótipo útil)

- [ ] Abrir PDF local, múltiplas abas, renderização de páginas, miniaturas, zoom, navegação e rotação visual.
- [ ] Buscar e copiar texto; lidar com PDF protegido e corrompido.
- [ ] Interface não congelar ao carregar documento grande; loading e cancelamento quando aplicáveis.

**Aceitação M1:** T01–T05 e casos básicos de UI passando.

### M2 — Ferramentas de páginas (primeiro MVP publicável como prévia)

- [ ] Mesclar, dividir, extrair, reordenar, girar e excluir páginas.
- [ ] Prévia antes de gravar, `Salvar como`, salvamento temporário/atômico, proteção do original.
- [ ] Desfazer/refazer para ações suportadas e mensagens de confirmação.
- [ ] Testes de integridade dos PDFs gerados.

**Aceitação M2:** T06–T11, T22; saída pode ser reaberta sem erros.

### M3 — Edição de documentos

- [ ] Destaques, comentários, carimbos, caixas de texto, formas, imagens e seleção.
- [ ] Preenchimento de formulários compatíveis.
- [ ] Persistência, desfazer/refazer e suporte a navegação contínua.
- [ ] Alerta ao editar PDF assinado.

**Aceitação M3:** T12, T15 e regressão de todas as operações de M1/M2.

### M4 — OCR, conversão e processamento em lote

- [ ] Adaptador Tesseract/OCRmyPDF (dependência verificável/opt-in).
- [ ] OCR em pt-BR/inglês, PDF pesquisável, conversão PDF/imagem e imagem/PDF.
- [ ] Otimizador básico, fila de tarefas com progresso/cancelamento/log.
- [ ] Conversão via LibreOffice como integração opcional, se tecnicamente validada.

**Aceitação M4:** T13, T14, T18 e testes de qualidade/falhas por arquivo.

### M5 — Recursos profissionais e segurança (sem prometer mágica)

- [ ] Remoção de metadados, ajustes de segurança e criptografia.
- [ ] Assinatura visual com aviso adequado.
- [ ] Protótipo + testes rigorosos antes de habilitar redação definitiva.
- [ ] Assinatura digital via pyHanko, se validada em separado.
- [ ] Pesquisar edição do texto já existente como funcionalidade de risco, separada de caixas de texto.

**Aceitação M5:** auditoria de dados e assinaturas; recursos que não passam nos critérios ficam indisponíveis.

### M6 — Distribuição e estabilização

- [ ] Empacotar build Windows sem Python global, gerar instalador e testar máquina limpa.
- [ ] Incluir licença/avisos de terceiros e guia de instalação/ajuda offline.
- [ ] Testar atualização e desinstalação, configurar política de versões e changelog.
- [ ] Testes de regressão, UI, performance e segurança, documentação honesta das limitações.
- [ ] Ubuntu Linux após estabilização Windows e verificação da distribuição de dependências.

**Aceitação M6:** instalação, abertura, manipulação e desinstalação verificadas com evidências; nenhum recurso falso no release.

---

## 9. Definição de pronto (Definition of Done)

Uma tarefa só está pronta se:

1. O comportamento foi implementado, não apenas exibido na UI.
2. Possui teste automático relevante e, quando visual, teste manual documentado.
3. Suas falhas têm tratamento e mensagem para o usuário.
4. Sua operação não compromete o original sem consentimento.
5. Está conectada ao menu/atalho correspondente e à ajuda.
6. Não introduz chamadas externas desnecessárias.
7. Documentação e changelog foram atualizados.
8. Compatibilidade e licenças das dependências foram verificadas.

### 9.1 Não aceitar como entregue

- Interface de fachada com botões simulados.
- Funções que silenciosamente não fazem nada.
- Marcas-d'água, contas ou cobranças.
- Edição destrutiva sem prévia, salvamento seguro ou alertas.
- OCR que somente desenha texto visual, sem torná-lo pesquisável.
- 'Redação' feita por retângulo preto sobre conteúdo que continua extraível.
- Assinatura desenhada vendida como assinatura digital validada.
- Afirmação de testes que o ambiente não executou.

---

## 10. Instruções ao agente de programação

1. **Comece por M0.** Não implemente M0–M6 numa única solicitação.
2. Antes de escrever código, verifique ferramentas, bibliotecas e ambiente disponível e registre riscos e decisões em `docs/decisions/`.
3. Apresente um plano curto com arquivos a criar/alterar e critérios de teste.
4. Faça alterações por fatias verticais: comportamento interno + interface + teste.
5. Execute os testes reais; reporte comandos, resultados e limitações, sem inventar sucesso.
6. Sempre que um serviço externo opcional estiver ausente, use capability-check, desabilite a função e informe ao usuário; não finja execução.
7. Respeite o objetivo visual: programa desktop robusto com menus, painéis, status e atalhos; não uma landing page minimalista.
8. Antes de finalizar cada marco, realize revisão de bugs, regressões, licenças e documentação.
9. Não gere instalador final se não for possível executar o teste de instalação; entregue scripts e indique a pendência.
10. Preserve o trabalho existente e peça confirmação antes de ações que apaguem dados do projeto.

---

## 11. Riscos e mitigação

| Risco | Impacto | Mitigação |
|---|---|---|
| Escopo excessivo | Projeto incompleto | Marcos pequenos, M0–M2 antes de extras |
| Edição de texto nativo PDF complexa | Layout quebrado | Adiar, prototipar e advertir limitações |
| Licenciamento PyMuPDF/Qt | Distribuição incompatível | Projeto aberto AGPL, inventário de dependências, checagem de licenças |
| PDF malformado ou malicioso | Crash ou exposição | Processos isolados, atualizações e limites de recursos |
| Salvamento incompleto | Perda de dados | Temporários, validação, original intocado e backups opcionais |
| OCR ruim | Erros documentais | Idiomas, resolução, prévia e avisos de confiabilidade |
| PDFs assinados | Invalidação de assinatura | Detecção, avisos e tratamento específico |
| Redação visual insuficiente | Vazamento de dados | Testes extração/raster/estrutura; função desabilitada até comprovada |
| Instalador pesado ou dependências ausentes | Experiência ruim | Auditoria de empacotamento e testes em VM limpa |
| Interface complexa demais para iniciantes | Curva de aprendizado | Assistentes para operações comuns sem remover opções avançadas |

---

## 12. Primeira sessão de Claude Code: entrega exigida

**Tarefa imediata: M0, somente M0.** Ao fim, esperamos:

- Janela principal real em português-BR, com barra de menus, barras de ferramentas, dock de miniaturas, dock de propriedades, abas, fila de tarefas e barra de status.
- Temas Classic Light e Graphite Pro, sem minimalismo exagerado.
- Persistência local das configurações de geometria, dock layout e tema.
- Contratos de serviço, registro de capacidades e classes de domínio iniciais.
- Testes automatizados que abrem a aplicação e validam estado/persistência.
- `README.md` com requisitos, instalação local, execução e testes.
- `docs/test_report.md` com comandos executados e resultado.
- Nada de botões fingindo que os recursos PDF já existem. Módulos futuros ficam indisponíveis com explicação clara.

**Em seguida:** M1 (renderização e busca reais), M2 (operações de páginas) e assim sucessivamente, mediante confirmação do usuário.

---

## 13. Glossário

- **PDF textual:** PDF com texto codificado que pode ser selecionado ou extraído.
- **PDF digitalizado:** PDF que contém imagens de páginas, com ou sem camada OCR.
- **OCR:** reconhecimento óptico de caracteres.
- **Redação (redaction):** remoção real de conteúdo sensível, diferente de cobrir visualmente.
- **Assinatura visual:** marca desenhada no documento, sem prova criptográfica por si só.
- **Assinatura digital:** assinatura criptográfica com certificado e validação.
- **MVP:** conjunto mínimo de funções confiáveis para resolver um problema real.

**Fim da especificação v1.0.**
