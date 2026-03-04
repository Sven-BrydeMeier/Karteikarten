#!/usr/bin/env bash
#
# run_all.sh — Kompletter Workflow: Dependencies → OSM-Download → Kartengenerierung
#
# Verwendung:
#   chmod +x run_all.sh
#   ./run_all.sh              # Alles ausführen
#   ./run_all.sh --skip-deps  # Dependencies überspringen
#   ./run_all.sh --skip-osm   # OSM-Download überspringen (nutzt Cache oder Fallback-Gitter)
#   ./run_all.sh --maps-only  # Nur Karten generieren (keine deps, kein OSM)
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# --- Farben ---
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
BOLD='\033[1m'
NC='\033[0m'

# --- Flags ---
SKIP_DEPS=false
SKIP_OSM=false

for arg in "$@"; do
    case "$arg" in
        --skip-deps)  SKIP_DEPS=true ;;
        --skip-osm)   SKIP_OSM=true ;;
        --maps-only)  SKIP_DEPS=true; SKIP_OSM=true ;;
        --help|-h)
            echo "Verwendung: $0 [--skip-deps] [--skip-osm] [--maps-only]"
            echo ""
            echo "  --skip-deps   Keine Python-Pakete installieren"
            echo "  --skip-osm    Kein OSM-Download (nutzt vorhandenen Cache)"
            echo "  --maps-only   Nur Karten generieren"
            exit 0
            ;;
        *)
            echo "Unbekannte Option: $arg"
            exit 1
            ;;
    esac
done

echo -e "${BOLD}${BLUE}"
echo "╔════════════════════════════════════════════════════════╗"
echo "║     Sylt Street Map Art — Kompletter Workflow         ║"
echo "╚════════════════════════════════════════════════════════╝"
echo -e "${NC}"

START_TOTAL=$(date +%s)

# ─── Schritt 1: Dependencies ──────────────────────────────────────────────────
if [ "$SKIP_DEPS" = false ]; then
    echo -e "${BOLD}[1/3] Dependencies installieren...${NC}"

    # Basis-Dependencies für die Karten (matplotlib)
    pip install --quiet matplotlib

    # Optionale Dependencies für OSM-Download
    if [ "$SKIP_OSM" = false ]; then
        echo "  → Installiere osmnx + geopandas (für OSM-Download)..."
        pip install --quiet osmnx geopandas
    fi

    echo -e "${GREEN}  ✓ Dependencies installiert${NC}\n"
else
    echo -e "${YELLOW}[1/3] Dependencies übersprungen (--skip-deps)${NC}\n"
fi

# ─── Schritt 2: OSM-Daten herunterladen ───────────────────────────────────────
if [ "$SKIP_OSM" = false ]; then
    echo -e "${BOLD}[2/3] OSM-Straßendaten herunterladen...${NC}"

    if [ -f "$SCRIPT_DIR/osm_streets_cache.json" ]; then
        SIZE=$(du -h "$SCRIPT_DIR/osm_streets_cache.json" | cut -f1)
        echo -e "${YELLOW}  Cache existiert bereits ($SIZE). Überschreibe...${NC}"
    fi

    python3 "$SCRIPT_DIR/download_osm_streets.py"

    if [ -f "$SCRIPT_DIR/osm_streets_cache.json" ]; then
        SIZE=$(du -h "$SCRIPT_DIR/osm_streets_cache.json" | cut -f1)
        echo -e "${GREEN}  ✓ OSM-Daten gespeichert ($SIZE)${NC}\n"
    else
        echo -e "${RED}  ✗ Download fehlgeschlagen — Fallback auf generierte Gitter${NC}\n"
    fi
else
    echo -e "${YELLOW}[2/3] OSM-Download übersprungen (--skip-osm)${NC}"
    if [ -f "$SCRIPT_DIR/osm_streets_cache.json" ]; then
        SIZE=$(du -h "$SCRIPT_DIR/osm_streets_cache.json" | cut -f1)
        echo -e "  Cache vorhanden: $SIZE\n"
    else
        echo -e "  Kein Cache — Fallback-Gitter wird verwendet\n"
    fi
fi

# ─── Schritt 3: Alle 7 Karten generieren ─────────────────────────────────────
echo -e "${BOLD}[3/3] Karten generieren...${NC}"

python3 "$SCRIPT_DIR/generate_all.py"

# ─── Zusammenfassung ──────────────────────────────────────────────────────────
END_TOTAL=$(date +%s)
ELAPSED=$((END_TOTAL - START_TOTAL))
MINUTES=$((ELAPSED / 60))
SECONDS=$((ELAPSED % 60))

echo ""
echo -e "${BOLD}${GREEN}"
echo "╔════════════════════════════════════════════════════════╗"
echo "║  Fertig! Gesamtdauer: ${MINUTES}m ${SECONDS}s"
echo "╚════════════════════════════════════════════════════════╝"
echo -e "${NC}"

# Ausgabe-Ordner anzeigen
if [ -d "$SCRIPT_DIR/output" ]; then
    echo "Erzeugte Karten in: $SCRIPT_DIR/output/"
    ls -lh "$SCRIPT_DIR/output/"*.png 2>/dev/null || true
fi
