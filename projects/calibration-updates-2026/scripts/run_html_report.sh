#!/usr/bin/env bash
# run_html_report.sh
#
# Build (or rebuild) the Phase-3 HTML assessment report.
# Run from the repo root with:
#
#   bash projects/calibration-updates-2026/scripts/run_html_report.sh
#
# ─────────────────────────────────────────────────────────────────────────────
# WHAT THIS SCRIPT DOES (end-to-end)
# ─────────────────────────────────────────────────────────────────────────────
#
#  1. Runs the three upstream pipeline scripts in sequence:
#       • build_phase2_isolation_tables.py  — rebuild phase-2 CSVs
#       • build_leakage_cube.py             — rebuild leakage_cube.nc
#       • plot_leakage_footprint.py         — regenerate footprint PNGs (dL + QU)
#
#  2. Generates a PAF beam-overlay PNG for every SB_REF in the manifest.
#
#  3. Generates a PAF beam-scan MP4 movie for every SB_REF in the manifest.
#
#  4. Writes the full HTML report to:
#       <DATA_ROOT>/phase3/index.html
#
#  If --package is given, step 5 runs AFTER the full local report is
#  already complete:
#
#  5. Assembles a self-contained shareable directory that contains:
#       • plots/        — PAF overlay PNGs, footprint PNGs, PAF movie MP4s
#       • media/        — combined-beams PNGs + leakage-stats PNGs + MP4s
#                         (no GIFs, no PDFs)
#       • leakage_cube.nc
#       • index.html    — patched copy: GIF buttons removed, cube href fixed,
#                         "Supporting CSV tables" and "Run summary" sections
#                         stripped (those reference local pipeline outputs)
#
#  NOTE: --package does NOT skip or bypass the local report build.
#  It always builds the complete local report first, then copies a
#  cleaned subset to the package directory.  The package is suitable
#  for handing to a collaborator or uploading to a shared drive — it
#  works as a stand-alone folder with no external dependencies.
#
# ─────────────────────────────────────────────────────────────────────────────
# WHAT IS INCLUDED / EXCLUDED IN THE SHAREABLE PACKAGE
# ─────────────────────────────────────────────────────────────────────────────
#
#  Included:
#    plots/paf_beam_overlay_<sbref>.png     PAF beam-overlay static images
#    plots/paf_beam_movie_<sbref>.mp4       PAF beam-scan movies
#    plots/footprint_dL_<field>.png         Leakage footprint ΔL maps
#    plots/footprint_QU_<field>.png         Leakage footprint |Q|,|U| maps
#    media/SB_REF-<sbref>/combined_beams*.png
#    media/SB_REF-<sbref>/leakage_stats*.png
#    media/SB_REF-<sbref>/*.mp4
#    leakage_cube.nc
#    index.html  (patched — see above)
#
#  Excluded (stripped to keep the package portable and compact):
#    *.gif            — animated GIFs (large; MP4 equivalents are included)
#    *.pdf            — source PDF figures
#    tables/*.csv     — pipeline CSVs (contain local absolute paths)
#    "Supporting CSV tables" and "Run summary" HTML sections
#
# ─────────────────────────────────────────────────────────────────────────────
# CASDA CREDENTIALS (for POSSUM AS203 selavy catalog)
# ─────────────────────────────────────────────────────────────────────────────
#
#  The polarised-source overlay tries POSSUM AS203 first (CASDA staged
#  download of selavy polarisation XML).  If credentials are absent it
#  falls back to Taylor et al. 2009 (VizieR J/ApJ/702/1230).
#
#  Option A — environment variables (export before running this script):
#    export CASDA_USER=your@email.edu.au
#    export CASDA_PASSWORD=yourpassword
#
#  Option B — ~/.netrc (persists across sessions):
#    echo "machine casda.csiro.au login your@email.edu.au password yourpassword" \
#        >> ~/.netrc && chmod 600 ~/.netrc
#
# ─────────────────────────────────────────────────────────────────────────────

set -euo pipefail

# Resolve the real location of this script, following symlinks.
# Uses Python (already a dependency) for macOS-portable realpath.
SCRIPTS="$(python3 -c 'import os,sys; print(os.path.dirname(os.path.realpath(sys.argv[1])))' "$0")"
REPO_ROOT="$(cd "${SCRIPTS}/../../.." && pwd)"
MANIFEST_FILE="${SCRIPTS}/../manifests/sb_manifest_reffield_average.txt"

while [[ $# -gt 0 ]]; do
    case "$1" in
        --manifest)
            MANIFEST_FILE="$2"
            shift 2
            ;;
        *)
            echo "ERROR: Unknown argument '$1'"
            exit 1
            ;;
    esac
done

# DATA_ROOT is read from LOCAL_BASE in the manifest.
# Hardcoded fallback (last used: reffield-average-qcorr):
DATA_ROOT="${HOME}/DATA/reffield-average-qcorr"
if [[ -f "${MANIFEST_FILE}" ]]; then
    _local_base=$(awk -F'=' '/^LOCAL_BASE=/{gsub(/[[:space:]]/,"",$2); print $2}' "${MANIFEST_FILE}" | tail -1)
    [[ -n "${_local_base}" ]] && DATA_ROOT="${_local_base}"
fi
echo "INFO - DATA_ROOT: ${DATA_ROOT}"

# Activate the repo's virtual environment.
source "${REPO_ROOT}/.venv/bin/activate"

# ─────────────────────────────────────────────────────────────────────────────
# QUICK HTML-ONLY REBUILD (skips all upstream pipeline steps)
# Use this to preview HTML/CSS/layout changes without re-running the pipeline.
# ─────────────────────────────────────────────────────────────────────────────
 python3 "${SCRIPTS}"/build_phase3_html_report.py \
     --data-root          "${DATA_ROOT}" \
     --manifest           "${MANIFEST_FILE}" \
     --start-index        30 \
     --end-index          33 \
     --pol-sources \
     --highlight-frac-pol 0.10 \
     --package           "${DATA_ROOT}/final_mvp_share" \

# ─────────────────────────────────────────────────────────────────────────────
# ACTIVE COMMAND — standard rebuild with polarised-source overlays
# ─────────────────────────────────────────────────────────────────────────────
#python3 "${SCRIPTS}"/build_phase3_html_report.py \
#    --data-root          "${DATA_ROOT}" \
#    --start-index        14 \
#    --end-index          49 \
#    --exclude-indices    "24-29" \
#    --pol-sources \
#    --highlight-frac-pol 0.10 \
#    --package           "${DATA_ROOT}/final_mvp_share" \
#    --html-only \
#    --force

echo ""
echo "Report written to:  ${DATA_ROOT}/phase3/index.html"
echo "Package written to: ${DATA_ROOT}/final_mvp_share/"

# ─────────────────────────────────────────────────────────────────────────────
# ALL AVAILABLE OPTIONS (uncomment and combine as needed)
# ─────────────────────────────────────────────────────────────────────────────

# ── Paths ─────────────────────────────────────────────────────────────────────

# --data-root /path/to/reffield-average
#     Top-level data directory.  Defaults to ~/DATA/reffield-average.
#     Expects phase2/ and SB_REF-*/ subdirectories.

# --phase2-dir /path/to/phase2
#     Path to Phase-2 outputs.  Defaults to <data-root>/phase2.

# --output-dir /path/to/phase3
#     Where the HTML report and all generated assets are written.
#     Defaults to <data-root>/phase3.

# --manifest /path/to/sb_manifest_reffield_average.txt
#     Explicitly set the manifest.  If omitted, the script searches
#     <repo>/projects/calibration-updates-2026/manifests/ then <data-root>.

# ── Manifest row selection (for master CSV rebuild) ──────────────────────────

# --start-index N
#     First manifest row index (0-based) to include when regenerating
#     leakage_master_table.csv.  Default: 0.

# --end-index N
#     Last manifest row index (inclusive) to include.  Default: 999 (all rows).

# --exclude-indices RANGES
#     Comma-separated indices or ranges to skip, e.g. '24-29' or '24-29,31'.
#     Rows in the existing master CSV are preserved for excluded indices.

# ── Regeneration ──────────────────────────────────────────────────────────────

# --html-only
#     Skip ALL upstream steps (master CSV rebuild, phase-2 tables, cube,
#     footprints, PAF overlay PNGs and movies).  Reads existing data files
#     and only regenerates index.html.  Fast — useful for layout/CSS previews.

# --force
#     Regenerate PAF overlay PNGs and beam-scan movies even if existing.
#     Omit for faster incremental rebuilds (existing files are reused).

# ── Polarised-source overlay ──────────────────────────────────────────────────

# --pol-sources
#     Overlay polarised sources on PAF overlay PNGs and beam-scan movies.
#     Catalog priority chain: POSSUM AS203 (CASDA) → Taylor 2009 (VizieR)
#                              → ATNF pulsars (VizieR B/psr/psr)

# --catalog-dir /path/to/catalogs
#     Directory for cached catalog CSVs (default: <output-dir>/catalogs).
#     Re-use a previously populated directory to skip VizieR entirely.

# --highlight-frac-pol 0.10
#     Draw a YlOrRd outer ring on sources with frac_pol >= threshold (0–1).
#     Sources below threshold are dimmed to 30% alpha.
#     Omit to show all sources at uniform full alpha with no rings.
#     Useful values: 0.05 (anything noticeably polarised), 0.10, 0.20

# ── HTML asset links ──────────────────────────────────────────────────────────

# --asset-http-base http://localhost:8000
#     HTTP base URL for clickable plot links in the report.
#     Pair with: python3 -m http.server 8000 --directory ~/DATA

# --asset-root /path/to/serve/root
#     Filesystem root corresponding to --asset-http-base.  Defaults to $HOME.

# ── Shareable package (built AFTER the full local report) ─────────────────────

# --package /path/to/phase3_mvp_share
#     The full local report is built first; then a cleaned copy is assembled
#     at this path (PNGs + MP4s + cube + patched index.html; no GIFs/CSVs).
#     The resulting directory is self-contained — hand it to a collaborator
#     or zip it:
#
#       python3 "${SCRIPTS}"/build_phase3_html_report.py \
#           --data-root          "${DATA_ROOT}" \
#           --pol-sources \
#           --highlight-frac-pol 0.10 \
#           --force \
#           --package            "${HOME}/Desktop/phase3_mvp_share"
#
#       zip -r phase3_mvp_share.zip "${HOME}/Desktop/phase3_mvp_share"
