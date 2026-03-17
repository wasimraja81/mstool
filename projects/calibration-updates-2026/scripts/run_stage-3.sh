#!/usr/bin/env bash
set -euo pipefail

# Resolve the real location of this script, following symlinks.
SCRIPTS="$(python3 -c 'import os,sys; print(os.path.dirname(os.path.realpath(sys.argv[1])))' "$0")"
MANIFESTS="${SCRIPTS}/../manifests"

"${SCRIPTS}"/assess_possum_1934s.sh \
  --manifest "${MANIFESTS}"/sb_manifest_reffield_average.txt \
  --start-index 2 --end-index 2 \
  --beam-start 0 --beam-end 3
