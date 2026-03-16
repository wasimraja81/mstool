#!/usr/bin/env bash
# run_paf_beam_overlay.sh
#
# Generate a static PAF beam overlay PNG using plot_paf_beam_overlay.py.
# Run from the repo root with:
#
#   bash projects/calibration-updates-2026/scripts/run_paf_beam_overlay.sh
#
# ─────────────────────────────────────────────────────────────────────────────

SCRIPTS="projects/calibration-updates-2026/scripts"
DATA_ROOT="/Users/raj030/DATA/reffield-average"
OUT_DIR="${DATA_ROOT}/phase3/plots"

mkdir -p "${OUT_DIR}"

# ── SB81084 REF_0324-28  (pol_axis=-45°, 920.5 MHz) ──────────────────────────
META="${DATA_ROOT}/SB_REF-81084_SB_1934-77045_SB_HOLO-76554_AMP_STRATEGY-multiply-insituPreflags/metadata"

# Basic overlay (beam centres + PAF elements, labels on)
python3 "${SCRIPTS}"/plot_paf_beam_overlay.py \
    --footprint  "${META}/footprintOutput-sb81084-REF_0324-28.txt" \
    --schedblock "${META}/schedblock-info-81084.txt" \
    --output     "${OUT_DIR}/paf_beam_overlay_81084.png"

echo "Saved → ${OUT_DIR}/paf_beam_overlay_81084.png"

# ── Same SB with sky reference markers ────────────────────────────────────────
# python3 "${SCRIPTS}"/plot_paf_beam_overlay.py \
#     --footprint  "${META}/footprintOutput-sb81084-REF_0324-28.txt" \
#     --schedblock "${META}/schedblock-info-81084.txt" \
#     --sky-markers \
#     --output     "${OUT_DIR}/paf_beam_overlay_81084_skymarkers.png"

# ── Override pol_axis manually (useful for debugging the transform) ────────────
# python3 "${SCRIPTS}"/plot_paf_beam_overlay.py \
#     --footprint  "${META}/footprintOutput-sb81084-REF_0324-28.txt" \
#     --schedblock "${META}/schedblock-info-81084.txt" \
#     --pol-axis 0.0 \
#     --output     "${OUT_DIR}/paf_beam_overlay_81084_pa0.png"

# ── No port labels (cleaner for presentations) ────────────────────────────────
# python3 "${SCRIPTS}"/plot_paf_beam_overlay.py \
#     --footprint  "${META}/footprintOutput-sb81084-REF_0324-28.txt" \
#     --schedblock "${META}/schedblock-info-81084.txt" \
#     --no-labels \
#     --output     "${OUT_DIR}/paf_beam_overlay_81084_nolabels.png"
