# ADR 0001 — Alicerce M0

Data: 04/11/2026. Estado: aceito para desenvolvimento do M0.

## Contexto e inspeção inicial

`D:\Projetos\DOC` estava vazio, sem Git e sem AGENTS.md no caminho de ancestrais.
Nenhum trabalho anterior foi substituído. Especificação v1 lida integralmente e
preservada em `docs/product_spec.md`. O pedido da sessão limita a execução a M0;
as funcionalidades dos demais marcos são requisitos futuros, não autorização
para implementá-las agora.

Sistema observado: Windows x64, NT 10.0.22631 (Windows 11), PowerShell.
`python --version` não encontrado; `py -0p`: nenhum Python instalado visível.
`uv 0.12.5` disponível. Cache padrão e um alias Python fora do projeto tiveram
acesso negado. Optou-se por Python 3.13.15 isolado em `.tools/python`, cache em
`.cache/uv` e ambiente `.venv`, sem alterar PATH ou instalar Python global.
O primeiro download com rede restrita falhou (10013); o download autorizado
posterior foi concluído. A aplicação não fará downloads.

## Decisões

- Monólito desktop modular: domínio puro Python; contratos/serviços de aplicação;
  adaptadores locais de persistência e detecção; widgets Qt. Sem servidor web,
  microserviços, conta, telemetria, atualizador ou acesso de rede na aplicação.
- Qt Widgets real: QMainWindow, QDockWidget, QTabWidget, QAction, QToolBar.
  QSettings em INI local com escrita atômica, nomes estáveis dos painéis e
  versionamento do layout. Nenhum PDF ou senha persistido no M0.
- Usar **PySide6-Essentials 6.12.0**, distribuição oficial que fornece o namespace
  `PySide6` com QtCore/QtGui/QtWidgets. Evitar o metapacote PySide6 6.12.0, que
  agora também puxa WebEngine/Pdf e Addons desnecessários. Não usar QtPdf como
  substituto oculto do motor escolhido. Ícones desenhados no próprio código.
- Python declarado >=3.12,<3.15; execução local em 3.13.15. Wheels oficiais Qt
  cp310-abi3 win_amd64 compatíveis com esse interpretador. Compatibilidade real
  das demais versões depende da matriz CI; não foi presumida como teste feito.
- PyMuPDF/MuPDF é a escolha de motor para M1, pela via AGPL. A versão atual
  consultada foi 2.1 (02/11/2026), Python >=3.11, wheel cp311-abi3 win_amd64.
  Seus novos requisitos incluem layout/ONNX/NumPy e exigem nova auditoria de
  licenças, dependências e segurança em M1. **Não instalado nem fixado no M0.**
- pikepdf, OCRmyPDF, Tesseract, LibreOffice, pyHanko e empacotadores permanecem
  adiados; nenhum é necessário para inicializar ou testar M0.
- Licença do código DocForge: AGPL-3.0-or-later, sem compra de licença comercial.
  PySide6/shiboken: opção LGPL-3.0 para os módulos usados, com avisos preservados
  e bibliotecas substituíveis. Essa escolha é compatível com o plano aberto AGPL;
  a distribuição de binários requer auditoria final dos artefatos, fontes
  correspondentes, avisos Qt e dependências transitivas. Não há instalador M0.
- Proteger também o caminho de configurações: INIs existentes precisam do
  identificador `application/id=docforge-ultimate` antes de qualquer escrita.
  PDFs e configurações de outros programas passados por engano são preservados
  byte a byte. Configuração irreconhecível requer um novo caminho, sem exclusão.
- Contratos de PDF não têm implementação de produção no M0. Recursos futuros
  ficam desabilitados e identificam o marco. Nenhuma sessão PDF fictícia na UI.
- JobService inicial oferece registro, transições e cancelamento cooperativo;
  sem executor de PDFs, tarefas simuladas ou threads artificiais em produção.
  Processos isolados, limites e cancelamento de I/O serão implementados no marco
  de processamento; seu contrato é preparado agora.
- CapabilitiesService inspeciona metadados de pacotes e caminhos de executáveis
  locais; não importa motores nem executa programas encontrados no PATH.
  Instalação detectada nunca significa recurso já implementado. Certificados
  são explicitamente “não inspecionados”; não se lê o repositório de certificados.

## Consulta antes da fixação

Metadados oficiais PyPI consultados em 04/11/2026: Essentials/shiboken 6.12.0,
pytest 9.2.0, pytest-qt 4.5.0, ruff 0.17.3, hatchling 1.33.0, build 1.6.1.
pytest e ferramentas: MIT. pytest-qt declara suporte a PySide6; a integração
com pytest 9.2.0 será comprovada pelos testes executados. O lock registra hashes
e dependências transitivas; `THIRD_PARTY_NOTICES.md` registra o inventário.

Fontes primárias:

- https://pypi.org/pypi/PySide6-Essentials/json
- https://pypi.org/pypi/PySide6/json
- https://doc.qt.io/qtforpython-6/package_details.html
- https://doc.qt.io/qt-6/licensing.html
- https://doc.qt.io/qt-6/supported-platforms.html
- https://pypi.org/project/pytest-qt/
- https://pypi.org/project/pytest/
- https://pypi.org/pypi/PyMuPDF/json
- https://pymupdf.readthedocs.io/en/latest/license.html
- https://www.gnu.org/licenses/agpl-3.0.html

O Qt 6.12 ainda lista Windows 10 1809+ e Windows 11 x64; isso não constitui teste
do DocForge no Windows 10. Nome/marca DocForge, instalador, compilação congelada
e revisão jurídica final continuam pendentes antes de publicação.

## Fatias de implementação e validação

1. Modelos, erros, contratos e serviços iniciais; testes unitários de invariantes,
   transições/cancelamento e detecção sem rede ou execução de binários.
2. Persistência e temas; testes de restauração em arquivo temporário e erros.
3. Janela clássica com ações reais do M0, painéis e abas de ajuda; testes pytest-qt
   de menus, atalhos, troca de tema e round-trip de geometria/layout.
4. Execução real Windows, verificação visual, smoke em processo separado,
   análise estática, build de fonte/wheel e relatório honesto de limitações.

Arquivos: `src/docforge/{domain,application,infrastructure,ui}`, `tests`,
`pyproject.toml`, `uv.lock`, `.github/workflows`, README/licença/avisos e `docs`.
