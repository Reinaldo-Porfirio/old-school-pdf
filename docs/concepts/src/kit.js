// Ícones vetoriais próprios em estilo anos 2000 e montagem da janela fictícia.
const DEFS = `<svg width="0" height="0" style="position:absolute"><defs>
<linearGradient id="gB" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#bfe2ff"/><stop offset=".5" stop-color="#4c9cf0"/><stop offset="1" stop-color="#1957b8"/></linearGradient>
<linearGradient id="gY" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#fff6c2"/><stop offset=".55" stop-color="#ffd650"/><stop offset="1" stop-color="#e09a12"/></linearGradient>
<linearGradient id="gY2" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#ffe98a"/><stop offset="1" stop-color="#f0ad1c"/></linearGradient>
<linearGradient id="gG" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#ffffff"/><stop offset=".6" stop-color="#c9d0d8"/><stop offset="1" stop-color="#8e98a4"/></linearGradient>
<linearGradient id="gGr" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#d6f7b0"/><stop offset=".5" stop-color="#6cc43a"/><stop offset="1" stop-color="#2f8a16"/></linearGradient>
<linearGradient id="gR" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#ffc2b8"/><stop offset=".5" stop-color="#e8483a"/><stop offset="1" stop-color="#a51a10"/></linearGradient>
<linearGradient id="gO" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#ffe2b0"/><stop offset=".5" stop-color="#ff9a2e"/><stop offset="1" stop-color="#d0620a"/></linearGradient>
<linearGradient id="gP" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#ffffff"/><stop offset="1" stop-color="#d8e0ea"/></linearGradient>
<linearGradient id="gW" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#b07a3a"/><stop offset=".5" stop-color="#e2b07a"/><stop offset="1" stop-color="#8a5622"/></linearGradient>
<linearGradient id="gV" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#e8d2ff"/><stop offset=".5" stop-color="#9a5ae0"/><stop offset="1" stop-color="#5a2a9a"/></linearGradient>
<radialGradient id="gGlass" cx=".35" cy=".3" r=".8"><stop offset="0" stop-color="#ffffff"/><stop offset=".5" stop-color="#cfe9ff"/><stop offset="1" stop-color="#6aa8e0"/></radialGradient>
<radialGradient id="gLogo" cx=".35" cy=".25" r=".9"><stop offset="0" stop-color="#ffe7a0"/><stop offset=".45" stop-color="#ff9a1e"/><stop offset="1" stop-color="#b0420a"/></radialGradient>
<linearGradient id="gShine" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#fff" stop-opacity=".85"/><stop offset="1" stop-color="#fff" stop-opacity="0"/></linearGradient>
</defs></svg>`;

const PAGE = (x = 5, y = 2, w = 14, h = 20) =>
  `<path d="M${x} ${y}h${w - 4}l4 4v${h - 4}h-${w}z" fill="url(#gP)" stroke="#5a6b80"/><path d="M${x + w - 4} ${y}v4h4" fill="#eef2f7" stroke="#5a6b80"/>`;

const ICONS = {
  home: `<path d="M12 3 2 11.5h3V21h5.5v-6h3v6H19v-9.5h3z" fill="url(#gO)" stroke="#8a3d06" stroke-linejoin="round"/><rect x="15.5" y="4" width="2.6" height="5" fill="#a5522a" stroke="#6a2a08"/>`,
  open: `<path d="M2 5h7l2 2h10v12H2z" fill="url(#gY2)" stroke="#97650a" stroke-linejoin="round"/><path d="M2 19 4.8 10H23l-2.6 9z" fill="url(#gY)" stroke="#97650a" stroke-linejoin="round"/>`,
  save: `<rect x="3" y="3" width="18" height="18" rx="2" fill="url(#gB)" stroke="#123f7a"/><rect x="7" y="3" width="10" height="6.5" fill="#eef3f9" stroke="#123f7a"/><rect x="13.5" y="4.2" width="2" height="4" fill="#123f7a"/><rect x="6" y="13" width="12" height="8" fill="#fff" stroke="#123f7a"/><path d="M8 16h8M8 18.5h6" stroke="#9ab"/>`,
  print: `<rect x="6" y="2.5" width="12" height="7" fill="#fff" stroke="#5a6470"/><rect x="2" y="9" width="20" height="9" rx="2" fill="url(#gG)" stroke="#3e4650"/><circle cx="18.5" cy="12" r="1" fill="#3c3"/><rect x="6" y="14.5" width="12" height="7" fill="#fff" stroke="#5a6470"/><path d="M8 17h8M8 19h6" stroke="#9ab"/>`,
  undo: `<path d="M10 4 3 10l7 6v-4h4.5a4.5 4.5 0 0 1 0 9H12v2.5h2.5a7 7 0 0 0 0-14H10z" fill="url(#gB)" stroke="#123f7a" stroke-linejoin="round"/>`,
  redo: `<g transform="translate(24 0) scale(-1 1)"><path d="M10 4 3 10l7 6v-4h4.5a4.5 4.5 0 0 1 0 9H12v2.5h2.5a7 7 0 0 0 0-14H10z" fill="url(#gGr)" stroke="#256a10" stroke-linejoin="round"/></g>`,
  zoomin: `<circle cx="10" cy="10" r="6.5" fill="url(#gGlass)" stroke="#2a3a4a" stroke-width="2"/><path d="M7 10h6M10 7v6" stroke="#1957b8" stroke-width="2"/><path d="M15 15l6 6" stroke="#8a5a1a" stroke-width="3.5" stroke-linecap="round"/>`,
  zoomout: `<circle cx="10" cy="10" r="6.5" fill="url(#gGlass)" stroke="#2a3a4a" stroke-width="2"/><path d="M7 10h6" stroke="#1957b8" stroke-width="2"/><path d="M15 15l6 6" stroke="#8a5a1a" stroke-width="3.5" stroke-linecap="round"/>`,
  search: `<circle cx="10" cy="10" r="6.5" fill="url(#gGlass)" stroke="#2a3a4a" stroke-width="2"/><path d="M6.5 8.5a4 4 0 0 1 3-2.5" stroke="#fff" stroke-width="1.5" fill="none"/><path d="M15 15l6 6" stroke="#8a5a1a" stroke-width="3.5" stroke-linecap="round"/>`,
  select: `<path d="M5 2v17l4.5-4 3 7 3-1.3-3-7H18z" fill="#fff" stroke="#111" stroke-linejoin="round"/>`,
  highlight: `<rect x="2" y="19" width="13" height="3.5" fill="#ffee30" stroke="#b9a000"/><path d="M14 2.5 21.5 10l-8.5 8.5-4.5 1 1-4.5z" fill="url(#gY)" stroke="#8a6a00" stroke-linejoin="round"/><path d="M9.5 15 13 18.5" stroke="#8a6a00"/>`,
  underline: `<path d="M7 3v8a5 5 0 0 0 10 0V3" fill="none" stroke="#1957b8" stroke-width="2.6"/><rect x="4" y="19" width="16" height="2.6" fill="#e8483a"/>`,
  comment: `<path d="M3 3.5h18v13h-9l-5 4.5v-4.5H3z" fill="url(#gY)" stroke="#97650a" stroke-linejoin="round"/><path d="M6.5 8h11M6.5 11h8" stroke="#97650a"/>`,
  textbox: `<rect x="3" y="4" width="18" height="16" fill="#fff" stroke="#3a4a5a"/><path d="M8 8.5h8M12 8.5v8" stroke="#1957b8" stroke-width="2.6"/><rect x="1.5" y="2.5" width="3" height="3" fill="#fff" stroke="#1957b8"/><rect x="19.5" y="18.5" width="3" height="3" fill="#fff" stroke="#1957b8"/>`,
  stamp: `<rect x="3.5" y="16" width="17" height="4.5" rx="1" fill="url(#gR)" stroke="#7a1a10"/><path d="M9 16v-4.5a3 3 0 1 1 6 0V16z" fill="url(#gW)" stroke="#5a3410"/><rect x="5" y="21" width="14" height="1.5" fill="#c8231a"/>`,
  shape: `<rect x="2.5" y="5" width="12" height="10" fill="url(#gB)" stroke="#123f7a"/><ellipse cx="15.5" cy="15" rx="6.5" ry="5.5" fill="url(#gGr)" stroke="#256a10" fill-opacity=".9"/>`,
  image: `<rect x="2" y="4" width="20" height="16" fill="#fff" stroke="#3a4a5a"/><rect x="4" y="6" width="16" height="12" fill="url(#gGlass)"/><path d="M4 18l5-6 4 4 3-3 4 5z" fill="url(#gGr)" stroke="#256a10" stroke-linejoin="round"/><circle cx="16" cy="9" r="1.8" fill="#ffd650"/>`,
  merge: `<rect x="2.5" y="2" width="10.5" height="14" fill="url(#gP)" stroke="#5a6b80"/><rect x="7.5" y="6" width="10.5" height="14" fill="url(#gP)" stroke="#5a6b80"/><circle cx="18" cy="18" r="5" fill="url(#gGr)" stroke="#256a10"/><path d="M18 15v6M15 18h6" stroke="#fff" stroke-width="2.2"/>`,
  split: `${PAGE()}<path d="M1.5 12.5h21" stroke="#d22" stroke-width="2" stroke-dasharray="3 2"/><path d="M8 7h8M8 9h6M8 16h8M8 18h5" stroke="#9ab"/>`,
  extract: `${PAGE(2, 2)}<path d="M5 8h6M5 10h7M5 13h5" stroke="#9ab"/><path d="M12 12h5V8.5l6 5.5-6 5.5V16h-5z" fill="url(#gO)" stroke="#8a3d06" stroke-linejoin="round"/>`,
  rotate: `<path d="M19 12a7 7 0 1 1-2.1-5" fill="none" stroke="#2f8a16" stroke-width="3"/><path d="M21.5 2.5v7h-7z" fill="url(#gGr)" stroke="#256a10" stroke-linejoin="round"/>`,
  remove: `${PAGE()}<circle cx="17" cy="17" r="5.5" fill="url(#gR)" stroke="#7a1a10"/><path d="M14.5 14.5l5 5M19.5 14.5l-5 5" stroke="#fff" stroke-width="2"/>`,
  lock: `<path d="M7 11V8a5 5 0 0 1 10 0v3" fill="none" stroke="#6a7480" stroke-width="2.6"/><rect x="4" y="11" width="16" height="11" rx="2" fill="url(#gY)" stroke="#8a6a00"/><circle cx="12" cy="15.5" r="1.8" fill="#6a4a00"/><path d="M12 16.5v3" stroke="#6a4a00" stroke-width="1.6"/>`,
  sign: `<path d="M2.5 20c3-4 4.5 1.5 7-1.5s3.5.5 6-1" fill="none" stroke="#1b3d8f" stroke-width="1.8" stroke-linecap="round"/><path d="M15 2.5l6.5 6.5-8 8-4.5 1 1-4.5z" fill="url(#gB)" stroke="#123f7a" stroke-linejoin="round"/>`,
  redact: `${PAGE()}<rect x="7" y="8" width="10" height="3" fill="#111"/><rect x="7" y="13" width="7" height="3" fill="#111"/><path d="M7 18.5h9" stroke="#9ab"/>`,
  meta: `${PAGE()}<circle cx="16" cy="16" r="5.5" fill="url(#gB)" stroke="#123f7a"/><path d="M16 14v5" stroke="#fff" stroke-width="2"/><circle cx="16" cy="12.6" r="1.1" fill="#fff"/>`,
  ocr: `${PAGE()}<text x="11.5" y="16.5" font-family="Georgia,serif" font-size="9" font-weight="bold" text-anchor="middle" fill="#1957b8">Aa</text><path d="M2 12.5h20" stroke="#25c22a" stroke-width="1.6"/>`,
  forms: `<rect x="3" y="2.5" width="18" height="19" fill="url(#gP)" stroke="#5a6b80"/><rect x="5.5" y="5.5" width="4" height="4" fill="#fff" stroke="#3a4a5a"/><path d="M6 7.5l1.4 1.4L11 5" stroke="#2f8a16" stroke-width="1.8" fill="none"/><rect x="5.5" y="12" width="4" height="4" fill="#fff" stroke="#3a4a5a"/><path d="M11.5 7.5h7M11.5 14h7M5.5 19h13" stroke="#8a9ab0" stroke-width="1.4"/>`,
  pdf: `<path d="M5 2h10l5 5v15H5z" fill="url(#gP)" stroke="#5a6b80"/><path d="M15 2v5h5" fill="#eef2f7" stroke="#5a6b80"/><rect x="2.5" y="11.5" width="15" height="6.5" rx="1" fill="url(#gR)" stroke="#7a1a10"/><text x="10" y="16.6" font-family="Arial" font-size="5.2" font-weight="bold" text-anchor="middle" fill="#fff">PDF</text>`,
  settings: `<circle cx="12" cy="12" r="8" fill="none" stroke="#5a6470" stroke-width="4.5" stroke-dasharray="3.1 3.2"/><circle cx="12" cy="12" r="7" fill="url(#gG)" stroke="#3e4650"/><circle cx="12" cy="12" r="2.8" fill="#fff" stroke="#3e4650"/>`,
  help: `<circle cx="12" cy="12" r="10" fill="url(#gB)" stroke="#123f7a"/><path d="M8.8 9a3.3 3.3 0 1 1 4.6 3c-1 .5-1.4 1-1.4 2.2" fill="none" stroke="#fff" stroke-width="2.4" stroke-linecap="round"/><circle cx="12" cy="17.6" r="1.4" fill="#fff"/>`,
  fit: `${PAGE(6, 3, 12, 18)}<path d="M2 12h3M19 12h3M3.5 10.5 2 12l1.5 1.5M20.5 10.5 22 12l-1.5 1.5" stroke="#1957b8" stroke-width="1.6" fill="none"/>`,
  continuous: `<rect x="5" y="1" width="14" height="10" fill="url(#gP)" stroke="#5a6b80"/><rect x="5" y="13" width="14" height="10" fill="url(#gP)" stroke="#5a6b80"/><path d="M7.5 4h9M7.5 6.5h7M7.5 16h9M7.5 18.5h7" stroke="#9ab"/>`,
  shield: `<path d="M12 2 4 5v6c0 5 3.5 9 8 11 4.5-2 8-6 8-11V5z" fill="url(#gB)" stroke="#123f7a" stroke-linejoin="round"/><path d="M8 12l3 3 5-6" stroke="#fff" stroke-width="2.4" fill="none" stroke-linecap="round"/>`,
  batch: `<rect x="6" y="2" width="14" height="16" fill="url(#gP)" stroke="#5a6b80"/><rect x="4" y="4" width="14" height="16" fill="url(#gP)" stroke="#5a6b80"/><rect x="2" y="6" width="14" height="16" fill="url(#gP)" stroke="#5a6b80"/><path d="M5 11h8M5 14h8M5 17h5" stroke="#9ab"/>`,
  compress: `${PAGE()}<path d="M12 4v5M9.5 6.5 12 9l2.5-2.5M12 20v-5M9.5 17.5 12 15l2.5 2.5" stroke="#d0620a" stroke-width="1.8" fill="none"/><path d="M8 12h8" stroke="#5a6b80" stroke-width="1.6"/>`,
  attach: `<path d="M16.5 7 9 14.5a2 2 0 0 0 2.8 2.8l8-8a4 4 0 0 0-5.6-5.6l-8.5 8.5a6 6 0 0 0 8.5 8.5L21 14" fill="none" stroke="#5a6470" stroke-width="2" stroke-linecap="round"/>`,
};

function icon(name, size = 24) {
  return `<svg width="${size}" height="${size}" viewBox="0 0 24 24">${ICONS[name] || ""}</svg>`;
}

// Logotipo provisório: página com selo dourado brilhante.
function logo(size = 18) {
  return `<svg width="${size}" height="${size}" viewBox="0 0 32 32">
    <path d="M6 2h14l7 7v21H6z" fill="url(#gP)" stroke="#2a3a55" stroke-width="1.4"/>
    <path d="M20 2v7h7" fill="#e6ecf3" stroke="#2a3a55" stroke-width="1.4"/>
    <path d="M10 10h8M10 13.5h12M10 17h7" stroke="#8aa0bb" stroke-width="1.6"/>
    <circle cx="19" cy="22" r="7.5" fill="url(#gLogo)" stroke="#7a2a06" stroke-width="1.4"/>
    <path d="m19 17.2 1.5 3 3.3.4-2.4 2.3.6 3.3-3-1.6-3 1.6.6-3.3-2.4-2.3 3.3-.4z" fill="#fff6d0" stroke="#8a3d06" stroke-width=".7"/>
    <ellipse cx="17" cy="18.5" rx="4.5" ry="2.2" fill="url(#gShine)" opacity=".7"/></svg>`;
}

const CAP = {
  min: `<svg width="10" height="10" viewBox="0 0 10 10"><rect x="1" y="7" width="7" height="2" fill="currentColor"/></svg>`,
  max: `<svg width="10" height="10" viewBox="0 0 10 10"><rect x="1" y="1" width="8" height="8" fill="none" stroke="currentColor" stroke-width="1.2"/><rect x="1" y="1" width="8" height="2" fill="currentColor"/></svg>`,
  close: `<svg width="10" height="10" viewBox="0 0 10 10"><path d="M1.5 1.5l7 7M8.5 1.5l-7 7" stroke="currentColor" stroke-width="2"/></svg>`,
};

const CHEV = `<svg width="9" height="9" viewBox="0 0 10 10"><path d="M2 5l3-3 3 3M2 8.5l3-3 3 3" fill="none" stroke="currentColor" stroke-width="1.4"/></svg>`;
const ARROW = (d) => `<svg width="8" height="8" viewBox="0 0 8 8"><path d="${d === "l" ? "M5.5 1 2 4l3.5 3z" : d === "r" ? "M2.5 1 6 4 2.5 7z" : "M1 2.5h6L4 6z"}" fill="currentColor"/></svg>`;

const MENUS = ["Arquivo", "Editar", "Exibir", "Documento", "Comentários", "Ferramentas", "OCR", "Segurança", "Janela", "Ajuda"];

function titlebar(cfg) {
  const t = cfg.title || "Caderno de revisão.pdf - DocForge Ultimate";
  return `<div class="titlebar"><span class="appicon">${logo(cfg.logoSize || 18)}</span><span class="title">${t}</span>
    <div class="caps"><b class="cap min">${CAP.min}</b><b class="cap max">${CAP.max}</b><b class="cap close">${CAP.close}</b></div></div>`;
}

function menubar(cfg) {
  const items = (cfg.menus || MENUS).map((m) => `<span><u>${m[0]}</u>${m.slice(1)}</span>`).join("");
  return `<div class="menubar">${cfg.menuPrefix || ""}${items}${cfg.menuSuffix || ""}</div>`;
}

function toolbar(items, cfg) {
  const out = items.map((it) => {
    if (it === "|") return `<span class="tsep"></span>`;
    if (it.combo) return `<span class="combo">${it.combo}${ARROW("d")}</span>`;
    const [ic, label, cls] = it;
    const show = label && (cfg.labels === true || (cfg.labels === "some" && cls && cls.includes("lab")));
    return `<span class="tbtn ${cls || ""}">${icon(ic, cfg.iconSize || 20)}${show ? `<span>${label}</span>` : ""}</span>`;
  });
  return `<div class="tb"><span class="grip"></span>${out.join("")}<span class="tb-end">${ARROW("d")}</span></div>`;
}

const TB1 = [["open", "Abrir", "lab"], ["save", "Salvar", "lab"], ["print", "Imprimir"], "|", ["undo", "Desfazer"], ["redo", "Refazer"], "|", ["select", "Selecionar", "on"], ["search", "Buscar", "lab"], "|", ["zoomout"], { combo: "75%" }, ["zoomin"], ["fit", "Ajustar"], ["continuous", "Contínua"], ["rotate", "Girar"]];
const TB2 = [["merge", "Mesclar", "lab"], ["split", "Dividir"], ["extract", "Extrair"], ["remove", "Excluir"], "|", ["highlight", "Destacar", "lab"], ["underline", "Sublinhar"], ["comment", "Comentário", "lab"], ["textbox", "Caixa de texto"], ["stamp", "Carimbo"], ["shape", "Formas"], ["image", "Imagem"], "|", ["forms", "Formulário", "lab"], ["ocr", "OCR", "lab"], "|", ["lock", "Proteger", "lab"], ["redact", "Redigir"], ["sign", "Assinar", "lab"]];

function miniPage(i) {
  const v = [
    `<div class="mh"></div><div class="mm"></div><div class="ml"></div><div class="ml" style="width:60px"></div><div class="mb"></div><div class="ml"></div><div class="ml" style="width:40px"></div>`,
    `<div class="mh"></div><div class="ml"></div><div class="ml"></div><div class="ml" style="width:50px"></div><div class="mb" style="height:34px"></div><div class="ml"></div>`,
    `<div class="mh"></div><div class="ml" style="width:70px"></div><div class="mb"></div><div class="mb"></div><div class="ml"></div>`,
    `<div class="mh"></div><div class="ml"></div><div class="ml" style="width:66px"></div><div class="ml"></div><div class="mb" style="height:26px"></div>`,
  ];
  return `<div class="mini">${v[i % 4]}</div>`;
}

function thumbs(n = 4) {
  let h = "";
  for (let i = 0; i < n; i++) {
    h += `<div class="thumb ${i === 0 ? "sel" : ""}">${miniPage(i)}<span>${i + 1}</span></div>`;
  }
  return `<div class="thumbs">${h}</div>`;
}

function pageHTML(extra = "") {
  const handles = [[-4, -4], ["calc(50% - 3px)", -4], ["calc(100% - 3px)", -4], [-4, "calc(100% - 3px)"], ["calc(50% - 3px)", "calc(100% - 3px)"], ["calc(100% - 3px)", "calc(100% - 3px)"], [-4, "calc(50% - 3px)"], ["calc(100% - 3px)", "calc(50% - 3px)"]]
    .map(([l, t]) => `<i style="left:${typeof l === "number" ? l + "px" : l};top:${typeof t === "number" ? t + "px" : t}"></i>`).join("");
  return `<div class="page">
    <div class="pg-head"><small>PROJETO ESTAÇÃO &nbsp;›&nbsp; CADERNO DE REVISÃO</small><h1>Resumo da vistoria</h1></div>
    <div class="pg-body">
      <p><mark>Conferir as medidas do corredor principal.</mark></p>
      <p>Manter livre a rota de circulação até a conclusão da segunda etapa de obras.</p>
      <div class="ln"></div><div class="ln" style="width:86%"></div><div class="ln" style="width:92%"></div>
      <div class="pg-box"><b>Equipe técnica</b><br>Responsável pela medição: <span class="pg-redact">Fulano de Tal 000.000</span><br>Amostra sintética para verificação.</div>
      <div class="ln" style="width:70%"></div><div class="ln"></div>
    </div>
    <div class="pg-sel">Medidas verificadas na segunda vistoria.${handles}</div>
    <span class="pg-note">${icon("comment", 22)}</span>
    <div class="pg-stamp">APROVADO</div>
    <div class="pg-sign">Responsável pela conferência<i>João Martins</i><u></u></div>
    <div class="pg-foot">Documento de demonstração &nbsp;/&nbsp; 01</div>
    ${extra}
  </div>`;
}

const DEFAULT_GROUPS = [
  { title: "Tarefas de página", special: true, links: [["merge", "Mesclar PDFs"], ["split", "Dividir documento"], ["extract", "Extrair páginas"], ["rotate", "Girar páginas"], ["remove", "Excluir páginas"]] },
  { title: "Comentar e marcar", links: [["highlight", "Destacar texto"], ["comment", "Adicionar comentário"], ["textbox", "Inserir caixa de texto"], ["stamp", "Aplicar carimbo"], ["image", "Inserir imagem"]] },
  { title: "Segurança", links: [["lock", "Proteger com senha"], ["redact", "Redigir informações"], ["sign", "Assinar digitalmente"], ["meta", "Remover metadados"]] },
  { title: "Detalhes", details: true },
];

function taskpane(cfg) {
  const groups = (cfg.groups || DEFAULT_GROUPS).map((g) => {
    const body = g.details
      ? `<div class="details"><b>Caderno de revisão.pdf</b><br>Documento PDF 1.7<br>4 páginas · 312 KB<br>Modificado: hoje, 13:03<br>3 anotações · 1 campo<br>Sem criptografia</div>`
      : g.links.map(([ic, l]) => `<a>${icon(ic, cfg.tpIcon || 16)}<span>${l}</span></a>`).join("");
    return `<div class="tg ${g.special ? "special" : ""}"><div class="tg-h"><span>${g.title}</span><i class="chev">${CHEV}</i></div><div class="tg-b">${body}</div></div>`;
  }).join("");
  return `<div class="rpane">${cfg.tpHead || ""}<div class="tp-scroll">${groups}</div></div>`;
}

function docArea(cfg) {
  return `<div class="docarea">
    <div class="doctabs"><span class="dtab">${icon("home", 16)}Início</span><span class="dtab on">${icon("pdf", 16)}Caderno de revisão.pdf *<b class="x">${CAP.close}</b></span><span class="dtab">${icon("pdf", 16)}Contrato 2004.pdf</span>${cfg.tabsSuffix || ""}</div>
    ${cfg.pagenav === false ? "" : `<div class="pagenav"><span class="nb">${ARROW("l")}</span><span>Página</span><span class="field">1</span><span>de 4</span><span class="nb">${ARROW("r")}</span><span class="grow"></span>${cfg.pagenavRight || "<span class=\"pn-info\">Alterações não gravadas</span>"}</div>`}
    <div class="canvas">${pageHTML(cfg.pageExtra)}${cfg.secondPage === false ? "" : `<div class="page"></div>`}${cfg.canvasExtra || ""}</div>
  </div>`;
}

function statusbar(cfg) {
  const cells = cfg.status || ["Pronto", "|", "Página 1 de 4", "|", "75%", "|", "Alterações não gravadas", "grow", "Local · Offline"];
  return `<div class="statusbar">${cells.map((c) => (c === "|" ? `<span class="ssep"></span>` : c === "grow" ? `<span class="grow"></span>` : `<span class="cell">${c}</span>`)).join("")}</div>`;
}

function buildApp(cfg) {
  const lp = `<div class="lpane"><div class="lp-h"><span>${cfg.lpTitle || "Páginas"}</span><b class="x">${CAP.close}</b></div>${cfg.lpTabs || ""}${thumbs()}</div>`;
  const top = cfg.ribbon || `<div class="toolbars">${toolbar(TB1, cfg)}${toolbar(TB2, cfg)}</div>`;
  const html = `${DEFS}<div class="stage">${cfg.backdrop || ""}<div class="win">
    ${titlebar(cfg)}${cfg.ribbon ? "" : menubar(cfg)}${top}
    <div class="main">${lp}${docArea(cfg)}${taskpane(cfg)}</div>
    ${statusbar(cfg)}</div>${cfg.overlay || ""}</div>`;
  document.body.innerHTML = html;
}
