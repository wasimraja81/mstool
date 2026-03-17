#!/usr/bin/env bash
set -euo pipefail

# Resolve the real location of this script, following symlinks.
SCRIPTS="$(python3 -c 'import os,sys; print(os.path.dirname(os.path.realpath(sys.argv[1])))' "$0")"
SLURM="${SCRIPTS}/../slurm"
MANIFESTS="${SCRIPTS}/../manifests"

"${SLURM}"/submit_pipeline.sh \
  --stage 1934 \
  --manifest "${MANIFESTS}"/sb_manifest_reffield_average.txt \
  --start-index 2 --end-index 2
