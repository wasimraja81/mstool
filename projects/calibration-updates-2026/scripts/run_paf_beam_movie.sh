#!/usr/bin/env bash
# run_paf_beam_movie.sh
#
# Run create_paf_beam_movie.sh for the calibration-updates-2026 project.
# Edit the active command below and execute from the repo root with:
#
#   bash projects/calibration-updates-2026/scripts/run_paf_beam_movie.sh
#
# ─────────────────────────────────────────────────────────────────────────────

SCRIPTS="projects/calibration-updates-2026/scripts"
MANIFEST="projects/calibration-updates-2026/manifests/manifest_ref_ws-4788.txt"

# ── Most common use-case: all active SBs (idx 14-49, excluding ODC-5233 24-29) ──
bash "${SCRIPTS}"/create_paf_beam_movie.sh \
    --manifest "${MANIFEST}" \
    --start-index 14 --end-index 49 --exclude-indices 24-29

# ── Single SB for a quick test ────────────────────────────────────────────────
# bash "${SCRIPTS}"/create_paf_beam_movie.sh \
#     --manifest "${MANIFEST}" \
#     --start-index 16 --end-index 16 \
#     --trail 0 --force

# ── Regenerate everything with Blues colourmap and slower playback ─────────────
# bash "${SCRIPTS}"/create_paf_beam_movie.sh \
#     --manifest "${MANIFEST}" \
#     --start-index 14 --end-index 49 --exclude-indices 24-29 \
#     --cmap Blues --fps 2 --force
