#!/usr/bin/env bash
# run_dQ_plots.sh
#
# Generate signed dQ (and optionally dU) vs beam-number plots, one figure
# per reference field selected by the manifest.
#
# Run from anywhere inside the repo with:
#
#   bash scratch/run_dQ_plots.sh
#
# ─────────────────────────────────────────────────────────────────────────────
# WHAT THIS SCRIPT DOES
# ─────────────────────────────────────────────────────────────────────────────
#
#  • Reads leakage_master_table.csv (built by build_phase1_master_table.py).
#  • Filters to the manifest-selected SB_REFs (default: indices 14–49,
#    excl 24–29) and derives the unique reference-field list from those rows.
#  • Generates one PNG per field per variant (regular / lcal) for dQ, and
#    optionally dU (--dU flag).
#  • Y-axis: symmetric floor at --ylim (default ±2.5 %); automatically
#    expands to accommodate any outliers beyond that bound.
#
#  Output directory (default):
#    <DATA_ROOT>/phase3/plots/dQ_vs_beam_<FIELD>_<variant>.png
#
# ─────────────────────────────────────────────────────────────────────────────
# CLI QUICK-REFERENCE  (python3 plot_dQ_vs_beam.py --help for full list)
# ─────────────────────────────────────────────────────────────────────────────
#
#  ── Manifest selection ──────────────────────────────────────────────────────
#  --manifest          Path to manifest file
#  --start-index N     First manifest row to include (default: 14)
#  --end-index   N     Last  manifest row to include (default: 49)
#  --exclude-indices   Comma-separated ranges to skip (default: "24-29")
#
#  ── Field selection ─────────────────────────────────────────────────────────
#  --fields STR        Comma-separated partial field names (e.g. "1324-28")
#                      Omit to plot all unique fields from the manifest
#
#  ── Variants ────────────────────────────────────────────────────────────────
#  --variant           regular | lcal | both  (default: both)
#
#  ── Quantities ──────────────────────────────────────────────────────────────
#  --dU                Also generate dU signed (%) figures
#
#  ── Y-axis ──────────────────────────────────────────────────────────────────
#  --ylim PCT          Minimum symmetric half-range in % (default: 2.5)
#                      Pass 0 to fully auto-scale
#
#  ── Display ─────────────────────────────────────────────────────────────────
#  --show              Open each figure interactively after saving
#
# ─────────────────────────────────────────────────────────────────────────────

set -euo pipefail

SCRIPTS="$(cd "$(dirname "$(python3 -c 'import os,sys; print(os.path.realpath(sys.argv[1]))' "$0")")" && pwd)"
DATA_ROOT="${HOME}/DATA/reffield-average"

REPO_ROOT="$(cd "${SCRIPTS}/../../.." && pwd)"
source "${REPO_ROOT}/.venv/bin/activate"

# ─────────────────────────────────────────────────────────────────────────────
# EXAMPLE A — single field, both variants, dQ only (default ylim ±2.5 %)
# ─────────────────────────────────────────────────────────────────────────────
python3 "${SCRIPTS}"/plot_dQ_vs_beam.py \
    --data-root        "${DATA_ROOT}" \
    --start-index      14 \
    --end-index        49 \
    --exclude-indices  "24-29" \
    --fields           "1324-28" \
    --variant          both

# ─────────────────────────────────────────────────────────────────────────────
# EXAMPLE B — all fields, both variants, dQ + dU, wider ylim floor
# ─────────────────────────────────────────────────────────────────────────────
#python3 "${SCRIPTS}"/plot_dQ_vs_beam.py \
#    --data-root        "${DATA_ROOT}" \
#    --start-index      14 \
#    --end-index        49 \
#    --exclude-indices  "24-29" \
#    --variant          both \
#    --dU \
#    --ylim             5.0

# ─────────────────────────────────────────────────────────────────────────────
# EXAMPLE C — two specific fields, regular variant only, auto-scale y-axis
# ─────────────────────────────────────────────────────────────────────────────
#python3 "${SCRIPTS}"/plot_dQ_vs_beam.py \
#    --data-root        "${DATA_ROOT}" \
#    --start-index      14 \
#    --end-index        49 \
#    --exclude-indices  "24-29" \
#    --fields           "1324-28,0324-28" \
#    --variant          regular \
#    --ylim             0
