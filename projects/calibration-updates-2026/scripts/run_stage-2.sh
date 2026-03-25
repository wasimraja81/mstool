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

usage() { cat <<EOF
Usage: $(basename "$0") [options]

Submits the 1934 science calibrator (stage 2) SLURM jobs.

Options:
  --manifest FILE   Manifest file (default: manifest_ref_ws-4788.txt)
  --start-index N   First manifest row index (0-based)
  --end-index N     Last manifest row index (inclusive)
  -h, --help        Show this help
EOF
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --manifest)    MANIFEST_FILE="$2"; shift 2 ;;
        --start-index) START_INDEX="$2";   shift 2 ;;
        --end-index)   END_INDEX="$2";     shift 2 ;;
        -h|--help) usage; exit 0 ;;
        *) echo "ERROR: Unknown argument '$1'"; exit 1 ;;
    esac
done

CMD=("${SLURM}"/submit_pipeline.sh --stage 1934 --manifest "${MANIFEST_FILE}")
[[ -n "${START_INDEX}" ]] && CMD+=(--start-index "${START_INDEX}")
[[ -n "${END_INDEX}" ]]   && CMD+=(--end-index "${END_INDEX}")

"${CMD[@]}"
