#!/usr/bin/env bash
set -euo pipefail

# Resolve the real location of this script, following symlinks.
SCRIPTS="$(python3 -c 'import os,sys; print(os.path.dirname(os.path.realpath(sys.argv[1])))' "$0")"
MANIFESTS="${SCRIPTS}/../manifests"

# ---------------------------------------------------------------------------
# CLI args — all optional; override as needed.
# --experiment baseline|qcorr  appends -qcorr to HPC_BASE_DIR when qcorr.
# Use cohorts/<name>.sh wrappers for reproducible per-experiment invocations.
# ---------------------------------------------------------------------------
MANIFEST_FILE="${MANIFESTS}/manifest_ref_ws-4788.txt"
START_INDEX=""
END_INDEX=""
BEAM_START=""
BEAM_END=""
EXPERIMENT="baseline"

while [[ $# -gt 0 ]]; do
    case "$1" in
        --manifest)    MANIFEST_FILE="$2"; shift 2 ;;
        --start-index) START_INDEX="$2";   shift 2 ;;
        --end-index)   END_INDEX="$2";     shift 2 ;;
        --beam-start)  BEAM_START="$2";    shift 2 ;;
        --beam-end)    BEAM_END="$2";      shift 2 ;;
        --experiment)  EXPERIMENT="$2";    shift 2 ;;
        *) echo "ERROR: Unknown argument '$1'"; exit 1 ;;
    esac
done

# Derive HPC_BASE_DIR, appending -qcorr suffix when experiment=qcorr.
_hpc_base=$(awk -F'=' '/^HPC_BASE_DIR=/{gsub(/[[:space:]]/,"",$2); print $2}' "${MANIFEST_FILE}" | tail -1)
if [[ "${EXPERIMENT}" == "qcorr" ]]; then
    _hpc_base="${_hpc_base}-qcorr"
fi

CMD=("${SCRIPTS}"/assess_possum_1934s.sh --manifest "${MANIFEST_FILE}")
[[ -n "${START_INDEX}" ]] && CMD+=(--start-index "${START_INDEX}")
[[ -n "${END_INDEX}" ]]   && CMD+=(--end-index "${END_INDEX}")
[[ -n "${BEAM_START}" ]]  && CMD+=(--beam-start "${BEAM_START}")
[[ -n "${BEAM_END}" ]]    && CMD+=(--beam-end "${BEAM_END}")
[[ -n "${_hpc_base}" ]]   && CMD+=(--hpc-base-dir "${_hpc_base}")

"${CMD[@]}"
