#!/usr/bin/env bash
set -euo pipefail

# Resolve the repo root from this script's real location (follows symlinks).
SCRIPTS="$(python3 -c 'import os,sys; print(os.path.dirname(os.path.realpath(sys.argv[1])))' "$0")"
REPO="${SCRIPTS}/../.."
MANIFESTS="${REPO}/manifests"

"${SCRIPTS}"/copy_and_combine_assessment_results.sh \
  --manifest "${MANIFESTS}"/sb_manifest_reffield_average.txt \
  --start-index 14 --end-index 49 \
  --exclude-indices 24-29 \
  --combine-only \
  --copy-metadata
