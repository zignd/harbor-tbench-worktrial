#!/usr/bin/env bash
# Render the PPTX to per-slide JPEGs for visual QA, and prove the render is of *this* deck.
#
#   bash scripts/render_deck.sh OUT_DIR
#
# Why this exists: LibreOffice's headless conversion fails silently often enough that a stale PDF
# from an earlier build survives, `pdftoppm` renders that, and the result looks like a perfectly good
# inspection of a deck that has since changed. That happened once during this audit - a corrected
# spend figure was still showing its old value in the "verified" render. So the freshness of the
# artifact is asserted here rather than assumed: the output directory is emptied first, and the PDF
# must be newer than the .pptx it claims to render.
#
# Renders outside the repository by default: slide images are inspection scratch, not
# deliverables, and the audit keeps committed binaries out of the tree. Costs nothing, runs
# no model calls. Exits non-zero if the render is missing or stale.
set -euo pipefail

cd "$(dirname "$0")/.."
PPTX="${1:-docs/result/presentation.pptx}"
OUT="${2:-${TMPDIR:-/tmp}/harbor-deck-render}"
# Resolve once, so an absolute argument still works after we cd into the output directory.
PPTX_ABS="$(cd "$(dirname "$PPTX")" && pwd)/$(basename "$PPTX")"

if [ ! -f "$PPTX" ]; then
  echo "no deck at $PPTX" >&2
  exit 1
fi
SOFFICE="/Applications/LibreOffice.app/Contents/MacOS/soffice"
command -v soffice >/dev/null 2>&1 && SOFFICE="$(command -v soffice)"
[ -x "$SOFFICE" ] || { echo "LibreOffice (soffice) not found" >&2; exit 1; }

# Empty the directory so a stale PDF can never survive into this run.
rm -rf "$OUT"
mkdir -p "$OUT"

# soffice writes into the current directory, so convert from inside it.
( cd "$OUT" && "$SOFFICE" --headless --convert-to pdf "$PPTX_ABS" >/dev/null 2>&1 ) || true

PDF="$OUT/$(basename "${PPTX%.pptx}").pdf"
[ -f "$PDF" ] || { echo "conversion produced no PDF at $PDF" >&2; exit 1; }

# The freshness assertion: a render that predates the deck proves nothing.
if [ "$PDF" -ot "$PPTX" ]; then
  echo "STALE RENDER: $PDF is older than $PPTX" >&2
  exit 1
fi

pdftoppm -jpeg -r 110 "$PDF" "$OUT/slide"
n=$(ls -1 "$OUT"/slide-*.jpg 2>/dev/null | wc -l | tr -d ' ')
[ "$n" -gt 0 ] || { echo "pdftoppm produced no images" >&2; exit 1; }

echo "rendered $n slide image(s) from $PPTX"
echo "  deck   $(shasum -a 256 "$PPTX" | cut -c1-12)  $(date -r "$PPTX" '+%H:%M:%S')"
echo "  pdf    $(shasum -a 256 "$PDF" | cut -c1-12)  $(date -r "$PDF" '+%H:%M:%S')  (newer: yes)"
echo "  images $OUT/slide-*.jpg"
