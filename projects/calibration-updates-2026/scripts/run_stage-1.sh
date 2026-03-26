#!/usr/bin/env bash
set -euo pipefail

# Resolve the real location of this script, following symlinks.
SCRIPTS="$(python3 -c 'import os,sys; print(os.path.dirname(os.path.realpath(sys.argv[1])))' "$0")"
SLURM="${SCRIPTS}/../slurm"
MANIFESTS="${SCRIPTS}/../manifests"

# ---------------------------------------------------------------------------
# CLI args — all optional; override as needed.
# Use cohorts/<name>.sh wrappers for reproducible per-experiment invocations.
# ---------------------------------------------------------------------------
MANIFEST_FILE="${MANIFESTS}/manifest_ref_ws-4788.txt"
START_INDEX=""
END_INDEX=""
EXPERIMENT=""
Q_CORR_VARIANT=""
Q_CORR_REF_WS=""
Q_CORR_ALLOW_MISMATCH=""

usage() { cat <<EOF
Usage: $(basename "$0") [options]

Submits the reference-field bandpass derivation (stage 1) SLURM jobs.

Options:
  --manifest FILE                  Manifest file (default: manifest_ref_ws-4788.txt)
  --start-index N                  First manifest row index (0-based)
  --end-index N                    Last manifest row index (inclusive)
  --experiment baseline|qcorr      Experiment type: drives Q-corrections and HPC output path
  --q-corr-variant bpcal|lcal      Correction variant (qcorr only; default: bpcal)
  --q-corr-ref-ws N                Override ref_ws for CSV row selection (escape hatch)
  --q-corr-allow-mismatch true     Allow ref_ws mismatch (escape hatch)
  -h, --help                       Show this help
EOF
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --manifest)              MANIFEST_FILE="$2";           shift 2 ;;
        --start-index)           START_INDEX="$2";             shift 2 ;;
        --end-index)             END_INDEX="$2";               shift 2 ;;
        --experiment)            EXPERIMENT="$2";              shift 2 ;;
        --q-corr-variant)        Q_CORR_VARIANT="$2";         shift 2 ;;
        --q-corr-ref-ws)         Q_CORR_REF_WS="$2";         shift 2 ;;
        --q-corr-allow-mismatch) Q_CORR_ALLOW_MISMATCH="$2"; shift 2 ;;
        -h|--help) usage; exit 0 ;;
        *) echo "ERROR: Unknown argument '$1'"; exit 1 ;;
    esac
done

CMD=("${SLURM}"/submit_pipeline.sh --stage ref --manifest "${MANIFEST_FILE}")
[[ -n "${START_INDEX}" ]]           && CMD+=(--start-index "${START_INDEX}")
[[ -n "${END_INDEX}" ]]             && CMD+=(--end-index "${END_INDEX}")
[[ -n "${EXPERIMENT}" ]]            && CMD+=(--experiment "${EXPERIMENT}")
[[ -n "${Q_CORR_VARIANT}" ]]        && CMD+=(--q-corr-variant "${Q_CORR_VARIANT}")
[[ -n "${Q_CORR_REF_WS}" ]]         && CMD+=(--q-corr-ref-ws "${Q_CORR_REF_WS}")
[[ -n "${Q_CORR_ALLOW_MISMATCH}" ]] && CMD+=(--q-corr-allow-mismatch "${Q_CORR_ALLOW_MISMATCH}")

"${CMD[@]}"
