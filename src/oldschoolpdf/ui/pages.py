"""Páginas de ajuda e diagnóstico locais, nunca apresentadas como documentos PDF."""

from html import escape

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QScrollArea,
    QTextBrowser,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from oldschoolpdf.application.capability_service import CapabilitiesService
from oldschoolpdf.ui.icons import app_icon, command_icon

GUIDE_HTML = """
<h1>Guia do Old School PDF</h1>
<p>Use <b>Arquivo → Abrir PDF</b> (Ctrl+O) ou solte arquivos locais na janela.
Cada PDF abre em uma aba. Se o arquivo for protegido, informe a senha na própria aba.</p>
<h2>Ler e navegar</h2>
<p>Clique em uma miniatura ou informe o número da página. Page Up e Page Down
mudam de página. Use a barra de zoom para escolher a escala, ajustar à página
ou ajustar à largura. Ctrl com a roda do mouse altera o zoom. A rotação muda
a orientação da visualização na aba. Ative <b>Exibir → Rolagem contínua</b>
para passar de uma página à outra pela roda do mouse ou pela barra de rolagem.</p>
<h2>Buscar e copiar</h2>
<p>Ctrl+F abre a busca. Digite o termo e pressione Enter. Use F3 e Shift+F3 para
navegar pelas ocorrências. A busca analisa a camada de texto do PDF. Para copiar,
arraste sobre uma área com Selecionar área de texto ativo e pressione Ctrl+C
na página. Sem uma área selecionada, o comando copia o texto da página.
As permissões do PDF determinam se a cópia está disponível.</p>
<h2>Organizar páginas</h2>
<p>Use <b>Documento → Mesclar PDFs</b> para escolher a ordem dos arquivos e conferir o total.
Em Dividir PDF, informe um intervalo por saída, como 1-3,4-8. Em Extrair páginas,
os intervalos indicados entram em um único PDF na ordem informada. Arraste miniaturas
ou use Reordenar páginas. Girar páginas do PDF aplica a rotação ao documento e atualiza a prévia.
O menu Documento também permite excluir intervalos da cópia de trabalho.</p>
<h2>Anotar e preencher</h2>
<p>Abra o painel <b>Propriedades e ferramentas → Edição</b> ou o menu Editar → Anotações.
Selecione o destaque, sublinhado, caixa de texto, carimbo, forma ou imagem e arraste sobre
a página. Clique para posicionar um comentário. Esc cancela a ferramenta ativa.
Selecione uma anotação na página ou no painel para mover, editar seu texto ou excluí-la,
conforme o tipo. Para campos AcroForm compatíveis, use Preencher formulário na página do campo.</p>
<h2>Gravar a cópia de trabalho</h2>
<p>Ctrl+Z e Ctrl+Y percorrem as revisões da aba. O asterisco no nome da aba indica alterações
pendentes. Use <b>Arquivo → Salvar como</b> (Ctrl+Shift+S) e escolha um destino separado.
Para substituir outro PDF existente, confirme a criação de uma cópia de segurança.
Ao fechar uma aba modificada, escolha salvar, descartar ou voltar à edição.
O aplicativo pede confirmação para editar ou exportar um PDF com indicação de assinatura
digital.</p>
<h2>Reconhecer texto em digitalizações</h2>
<p>Em <b>OCR → Configurar OCR local</b>, escolha a pasta tessdata com
por.traineddata ou eng.traineddata. Clique em Testar modelos e confirme os idiomas validados.
Em Reconhecer texto, escolha idioma, resolução, páginas e pasta de saída. O resultado mantém a
aparência da página e acrescenta texto pesquisável onde foi reconhecido. Revise os resultados,
principalmente em digitalizações de baixa qualidade.</p>
<h2>Converter, otimizar e processar lotes</h2>
<p>Em <b>Ferramentas</b>, exporte páginas para PNG ou JPEG, reúna imagens em um PDF,
extraia texto UTF-8 ou imagens incorporadas. Otimizar PDF compara o tamanho original com
o resultado. A redução de imagens é opcional e pode alterar a qualidade.</p>
<p><b>Processar lote</b> oferece as operações da lista em arquivos do disco. Use Salvar como
para incluir a revisão de uma aba editada. Cada entrada concluída recebe uma pasta nova.
O relatório mostra resultados e permite repetir falhas e cancelamentos.</p>
<h2>Proteger e assinar cópias</h2>
<p>Em <b>Segurança</b>, escolha quais campos da ficha Info e se quer remover o XMP.
Para restringir a abertura do PDF, grave uma cópia AES-256 com senhas distintas
de abertura e proprietário. A fila confirma a publicação de cada cópia.</p>
<p>Use <b>Marcar área para redação</b> (Ctrl+Alt+R) e arraste sobre cada ocorrência
sensível em qualquer página. Revise as marcas e exporte a cópia rasterizada.
O resultado perde busca, OCR, campos, links e assinaturas. A edição de uma revisão
limpa as marcas. A operação aceita PDFs sem criptografia de até 100 páginas.</p>
<p>Arraste a posição de uma <b>assinatura visual</b> e desenhe ou escolha PNG/JPEG.
Grave a revisão com Salvar como. Para assinar criptograficamente, habilite o extra
opcional <b>signing</b> e use seu arquivo PKCS#12. A verificação apresenta integridade,
cobertura e confiança com as raízes locais selecionadas.</p>
<h2>Organizar a área de trabalho</h2>
<p>Arraste os títulos dos painéis para encaixar, flutuar ou reorganizar.
Use Exibir → Painéis para mostrar ou ocultar cada um. As barras de ferramentas
também podem ser movidas e ocultadas. O menu de contexto das barras reúne essas opções.
Exibir → Restaurar organização padrão recupera a disposição original.</p>
<h2>Aparência e preferências</h2>
<p>O visual Clássico 2000 usa relevo 3D, ícones coloridos e painéis com barra de título.
Ferramentas → Preferências configura tamanho dos ícones, texto sob os ícones,
restauração do layout, cache de páginas e atalhos. Tema e layout são gravados localmente ao
alterar preferências ou fechar o programa. Se a gravação falhar, o aplicativo avisa.</p>
<h2>Abas e teclado</h2>
<p>Arraste uma aba para
reordenar. Ctrl+W fecha a aba atual; Ctrl+Tab e Ctrl+Shift+Tab navegam entre abas.
O menu Janela lista as páginas abertas. Ctrl+1 reabre o Início; F1 abre este guia.
</p>
<h2>Recursos locais</h2>
<p>Ajuda → Recursos locais consulta metadados de pacotes e procura executáveis
no PATH. Não executa ferramentas, lê certificados ou acessa a internet.
Um componente detectado ainda pode exigir validação e integração futura.</p>
<h2>Tarefas e documentos</h2>
<p>A fila mostra aberturas, buscas, exportações e lotes da sessão. Selecione uma tarefa
para cancelar ou use Cancelar lote em Ferramentas. Os resultados já publicados permanecem
disponíveis. Cada aba mantém página, rotação, zoom e revisões enquanto estiver aberta.</p>
<h2>Privacidade e licença</h2>
<p>Sem login, mensalidade, marca-d'água, telemetria ou uploads. Nenhum conteúdo
ativo de PDF é executado. Não há atualizações automáticas de rede.
Código sob AGPL-3.0-or-later, com avisos de terceiros preservados.</p>
"""


def section_label(text: str, size: int = 12) -> QLabel:
    label = QLabel(text)
    font = label.font()
    font.setPointSize(size)
    font.setBold(True)
    label.setFont(font)
    return label


class HomePage(QScrollArea):
    open_requested = Signal()
    guide_requested = Signal()
    preferences_requested = Signal()
    capabilities_requested = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("home_page")
        self.setWidgetResizable(True)
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)
        banner = QFrame()
        banner.setProperty("role", "workspaceHeader")
        banner_layout = QHBoxLayout(banner)
        symbol = QLabel()
        symbol.setPixmap(app_icon().pixmap(48, 48))
        banner_layout.addWidget(symbol)
        titles = QVBoxLayout()
        titles.addWidget(section_label(self.tr("Old School PDF"), 20))
        subtitle = QLabel(self.tr("Oficina de documentos • local, livre e sem cadastro"))
        subtitle.setWordWrap(True)
        titles.addWidget(subtitle)
        banner_layout.addLayout(titles, 1)
        layout.addWidget(banner)
        intro = QLabel(
            self.tr(
                "Leia, organize e edite PDFs locais. Proteja cópias com senha, revise áreas "
                "sensíveis e assine arquivos. Acompanhe as operações na fila de tarefas."
            )
        )
        intro.setWordWrap(True)
        layout.addWidget(intro)
        layout.addWidget(section_label(self.tr("Área de trabalho")))
        buttons = QHBoxLayout()
        for text, icon, callback in (
            (self.tr("Abrir PDF"), "open", self.open_requested.emit),
            (self.tr("Guia offline"), "info", self.guide_requested.emit),
            (self.tr("Preferências"), "settings", self.preferences_requested.emit),
            (self.tr("Recursos locais"), "shield", self.capabilities_requested.emit),
        ):
            button = QPushButton(command_icon(icon), text)
            button.clicked.connect(callback)
            buttons.addWidget(button)
        buttons.addStretch()
        layout.addLayout(buttons)
        layout.addWidget(section_label(self.tr("Roteiro de construção")))
        roadmap = QTreeWidget()
        roadmap.setObjectName("roadmap_tree")
        roadmap.setHeaderLabels([self.tr("Marco"), self.tr("Entrega"), self.tr("Estado")])
        roadmap.setRootIsDecorated(False)
        roadmap.setAlternatingRowColors(True)
        roadmap.setMinimumHeight(205)
        for row in (
            ("M0", "Janela, temas, painéis e contratos", "Concluído"),
            ("M1", "Visualizador e busca em PDFs", "Concluído"),
            ("M2", "Organização de páginas e exportação", "Concluído"),
            ("M3", "Anotações e formulários", "Concluído"),
            ("M4", "OCR, conversão e lotes", "Concluído"),
            ("M5", "Segurança e assinaturas locais", "Concluído"),
            ("M6", "Visual Clássico 2000, novo nome e instalador", "Versão atual"),
            ("M7", "Publicação e atualizações", "Futuro"),
        ):
            QTreeWidgetItem(roadmap, row)
        roadmap.header().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        roadmap.header().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        roadmap.header().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        layout.addWidget(roadmap, 1)
        note = QLabel(
            self.tr(
                "Comandos futuros estão identificados e desabilitados. "
                "O original é preservado quando você grava uma cópia de trabalho."
            )
        )
        note.setProperty("role", "muted")
        note.setWordWrap(True)
        layout.addWidget(note)
        self.setWidget(content)


class GuidePage(QTextBrowser):
    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("guide_page")
        self.setAcceptDrops(False)
        self.viewport().setAcceptDrops(False)
        self.setOpenExternalLinks(False)
        self.setOpenLinks(False)
        self.setHtml(GUIDE_HTML)
        self.document().setDocumentMargin(24)


class CapabilitiesPage(QWidget):
    def __init__(self, service: CapabilitiesService) -> None:
        super().__init__()
        self.setObjectName("capabilities_page")
        self.service = service
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 20, 20, 20)
        root.addWidget(section_label(self.tr("Recursos locais"), 18))
        note = QLabel(
            self.tr(
                "Diagnóstico offline. Detectar uma instalação não habilita operações futuras. "
                "O diagnóstico consulta os componentes instalados na máquina."
            )
        )
        note.setWordWrap(True)
        root.addWidget(note)
        self.tree = QTreeWidget()
        self.tree.setObjectName("capabilities_tree")
        self.tree.setRootIsDecorated(False)
        self.tree.setAlternatingRowColors(True)
        self.tree.setHeaderLabels(
            [self.tr("Componente"), self.tr("Disponibilidade"), self.tr("Detalhes")]
        )
        self.tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.tree.header().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.tree.header().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        root.addWidget(self.tree, 1)
        row = QHBoxLayout()
        button = QPushButton(command_icon("info"), self.tr("Atualizar diagnóstico local"))
        button.clicked.connect(self.refresh)
        row.addWidget(button)
        row.addStretch()
        root.addLayout(row)
        self.refresh()

    def refresh(self) -> None:
        self.tree.clear()
        for capability in self.service.check().items:
            if capability.implemented:
                state = self.tr("Disponível") if capability.detected else self.tr("Ausente")
                if capability.detected is None:
                    state = self.tr("Sob demanda")
            elif capability.key in {"signing", "certificates"}:
                state = self.tr("Requer extra signing")
            else:
                state = f"Futuro · {capability.milestone}"
            item = QTreeWidgetItem(self.tree, [capability.label, state, capability.detail])
            item.setToolTip(2, escape(capability.detail))
