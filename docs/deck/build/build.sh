#!/usr/bin/env bash
# Rebuild the deck: pptx, then pdf, then preview PNGs. Run from anywhere.
set -euo pipefail
cd "$(dirname "$0")"
DECK=../out/lumen-dispute-copilot-2026-10-29
SOFFICE="/c/Program Files/LibreOffice/program/soffice.exe"
PROFILE="C:/Users/mannk/AppData/Local/hermes/cache/scratch/lo-deck-profile"

python make_bare.py
node build.js
python fix_ppr.py "$DECK.pptx"
rm -f "$DECK.pdf"
rm -rf "/c/Users/mannk/AppData/Local/hermes/cache/scratch/lo-deck-profile"
"$SOFFICE" --headless --norestore --nologo -env:UserInstallation="file:///$PROFILE" \
  --convert-to pdf --outdir ../out "$DECK.pptx"
python render.py "$DECK.pdf"
python qa_deck.py "$DECK.pptx"
