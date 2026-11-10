#!/bin/sh
# Renderiza cada conceito HTML de src/ em PNG 1440x900 com o Edge headless.
# Uso: ./render.sh            (todos)   |   ./render.sh 03-aero   (um só)
EDGE="/c/Program Files (x86)/Microsoft/Edge/Application/msedge.exe"
cd "$(dirname "$0")"
base=$(pwd -W)
for f in src/${1:-[0-9]*}.html; do
  name=$(basename "$f" .html)
  "$EDGE" --headless=new --disable-gpu --hide-scrollbars --window-size=1440,900 \
    --screenshot="$(cygpath -w "$base/$name.png")" "file:///$base/$f" >/dev/null 2>&1
  echo "$name.png"
done
