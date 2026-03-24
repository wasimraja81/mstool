#!/usr/bin/env bash
set -euo pipefail

# Resolve the real location of this script, following symlinks.
SCRIPTS="$(python3 -c 'import os,sys; print(os.path.dirname(os.path.realpath(sys.argv[1])))' "$0")"
SLURM="${SCRIPTS}/../slurm"
MANIFESTS="${SCRIPTS}/../manifests"

Q_CORR_CSV="/askapbuffer/payne/raj030/askap-calibration-updates/dq_du_correction_factors.csv"

# ---------------------------------------------------------------------------
# Examples — uncomment the block you want and comment the rest.
# ---------------------------------------------------------------------------

# [1] ACTIVE — Standard Q-corrections run (bpcal, standard dQ/dU CSV)
"${SLURM}"/submit_pipeline.sh \
  --stage ref \
  --manifest "${MANIFESTS}"/sb_manifest_reffield_average.txt \
  --start-index 2 --end-index 2 \
  --apply-q-corrections true \
  --q-corr-csv "${Q_CORR_CSV}" \
  --q-corr-variant bpcal

# [2] Baseline run — Q-corrections disabled (produces unmodified bandpass table)
# "${SLURM}"/submit_pipeline.sh \
#   --stage ref \
#   --manifest "${MANIFESTS}"/sb_manifest_reffield_average.txt \
#   --start-index 2 --end-index 2 \
#   --apply-q-corrections false

# [3] Q-corrections with an updated CSV file (e.g. newly derived dQ/dU table)
# "${SLURM}"/submit_pipeline.sh \
#   --stage ref \
#   --manifest "${MANIFESTS}"/sb_manifest_reffield_average.txt \
#   --start-index 2 --end-index 2 \
#   --apply-q-corrections true \
#   --q-corr-csv /askapbuffer/payne/raj030/askap-calibration-updates/dq_du_correction_factors_v2.csv \
#   --q-corr-variant bpcal

# [4] Use lcal variant (leakage-calibrator-derived correction factors instead of bpcal)
# "${SLURM}"/submit_pipeline.sh \
#   --stage ref \
#   --manifest "${MANIFESTS}"/sb_manifest_reffield_average.txt \
#   --start-index 2 --end-index 2 \
#   --apply-q-corrections true \
#   --q-corr-csv "${Q_CORR_CSV}" \
#   --q-corr-variant lcal

# [5] Cross-survey reuse — override ref_ws to select rows from a different survey's dQ table
# "${SLURM}"/submit_pipeline.sh \
#   --stage ref \
#   --manifest "${MANIFESTS}"/sb_manifest_reffield_average.txt \
#   --start-index 2 --end-index 2 \
#   --apply-q-corrections true \
#   --q-corr-csv "${Q_CORR_CSV}" \
#   --q-corr-ref-ws 12345

# [6] Escape hatch — allow ref_ws mismatch (use with caution; logs a warning per beam)
# "${SLURM}"/submit_pipeline.sh \
#   --stage ref \
#   --manifest "${MANIFESTS}"/sb_manifest_reffield_average.txt \
#   --start-index 2 --end-index 2 \
#   --apply-q-corrections true \
#   --q-corr-csv "${Q_CORR_CSV}" \
#   --q-corr-allow-mismatch true
