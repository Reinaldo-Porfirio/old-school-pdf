# Conceitos visuais

Cinco direções para o tema da interface, todas no estilo de software dos anos 2000.
São maquetes em HTML/CSS com ícones vetoriais próprios, sem logotipos ou arte
de terceiros. Elas servem de referência para os temas Qt e não são telas reais do app.

| Arquivo | Direção | Referências da época |
|---|---|---|
| `01-luna.png` | **Luna Azul** | Windows XP Luna (2001), Office 2003 Blue, painel de tarefas do Explorer, balão de dica |
| `02-classico.png` | **Clássico 2000** | Windows 2000/Me, bordas 3D em relevo, leitores de PDF com abas verticais, diálogos cinza |
| `03-aero.png` | **Aero Faixa** | Windows Vista/7 Aero (2006–2009), faixa de opções do Office 2007, botão orbe, Frutiger Aero |
| `04-aqua.png` | **Aqua Gel** | Mac OS X Aqua (2000–2007), botões gel, listras finas, lista lateral, barra unificada |
| `05-midia.png` | **Skin Mídia** | Skins de players e programas de gravação: cromo, painel LCD, botões redondos, brilho azul |

## Como gerar de novo

Edite os arquivos em `src/` e rode no Git Bash:

```bash
./render.sh            # renderiza os cinco
./render.sh 03-aero    # renderiza um só
```

O script usa o Microsoft Edge em modo headless para gravar PNGs de 1440×900.
