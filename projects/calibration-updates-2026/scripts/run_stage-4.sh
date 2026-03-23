#!/usr/bin/env bash
set -euo pipefail

# Resolve the real location of this script, following symlinks.
SCRIPTS="$(python3 -c 'import os,sys; print(os.path.dirname(os.path.realpath(sys.argv[1])))' "$0")"
REPO_ROOT="$(cd "${SCRIPTS}/../../.." && pwd)"
MANIFESTS="${SCRIPTS}/../manifests"

# Activate the repo's virtual environment.
source "${REPO_ROOT}/.venv/bin/activate"

"${SCRIPTS}"/copy_and_combine_assessment_results.sh \
  --manifest "${MANIFESTS}"/sb_manifest_reffield_average.txt \
  --start-index 30 --end-index 30 \
  --copy-metadata
