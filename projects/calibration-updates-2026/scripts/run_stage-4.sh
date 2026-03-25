#!/usr/bin/env bash
set -euo pipefail

# Resolve the real location of this script, following symlinks.
SCRIPTS="$(python3 -c 'import os,sys; print(os.path.dirname(os.path.realpath(sys.argv[1])))' "$0")"
REPO_ROOT="$(cd "${SCRIPTS}/../../.." && pwd)"
MANIFESTS="${SCRIPTS}/../manifests"

MANIFEST_FILE="${MANIFESTS}/manifest_ref_ws-4788.txt"
START_INDEX=""
END_INDEX=""
EXPERIMENT="baseline"
COPY_METADATA="false"

while [[ $# -gt 0 ]]; do
    case "$1" in
        --manifest)      MANIFEST_FILE="$2"; shift 2 ;;
        --start-index)   START_INDEX="$2";   shift 2 ;;
        --end-index)     END_INDEX="$2";     shift 2 ;;
        --experiment)    EXPERIMENT="$2";    shift 2 ;;
        --copy-metadata) COPY_METADATA="true"; shift ;;
        *) echo "ERROR: Unknown argument '$1'"; exit 1 ;;
    esac
done

# Activate the repo's virtual environment.
source "${REPO_ROOT}/.venv/bin/activate"

# Derive effective LOCAL_BASE and HPC_BASE_DIR, applying -qcorr suffix when needed.
_local_base=$(awk -F'=' '/^LOCAL_BASE=/{gsub(/[[:space:]]/,"",$2); print $2}' "${MANIFEST_FILE}" | tail -1)
_hpc_base=$(awk -F'=' '/^HPC_BASE_DIR=/{gsub(/[[:space:]]/,"",$2); print $2}' "${MANIFEST_FILE}" | tail -1)
if [[ "${EXPERIMENT}" == "qcorr" ]]; then
    _local_base="${_local_base}-qcorr"
    _hpc_base="${_hpc_base}-qcorr"
fi

CMD=("${SCRIPTS}"/copy_and_combine_assessment_results.sh --manifest "${MANIFEST_FILE}")
[[ -n "${START_INDEX}" ]]  && CMD+=(--start-index "${START_INDEX}")
[[ -n "${END_INDEX}" ]]    && CMD+=(--end-index "${END_INDEX}")
[[ -n "${_local_base}" ]]  && CMD+=(--local-base "${_local_base}")
[[ -n "${_hpc_base}" ]]    && CMD+=(--remote-base "${_hpc_base}")
[[ "${COPY_METADATA}" == "true" ]] && CMD+=(--copy-metadata)

"${CMD[@]}"
