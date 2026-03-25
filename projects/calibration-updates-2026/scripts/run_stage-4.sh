#!/usr/bin/env bash
set -euo pipefail

# Resolve the real location of this script, following symlinks.
SCRIPTS="$(python3 -c 'import os,sys; print(os.path.dirname(os.path.realpath(sys.argv[1])))' "$0")"
REPO_ROOT="$(cd "${SCRIPTS}/../../.." && pwd)"
MANIFESTS="${SCRIPTS}/../manifests"

MANIFEST_FILE="${MANIFESTS}/manifest_ref_ws-4788.txt"

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

# Activate the repo's virtual environment.
source "${REPO_ROOT}/.venv/bin/activate"

"${SCRIPTS}"/copy_and_combine_assessment_results.sh \
  --manifest "${MANIFEST_FILE}" \
  --start-index 33 --end-index 33 \
  --copy-metadata
