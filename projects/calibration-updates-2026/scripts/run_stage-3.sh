#!/usr/bin/env bash
set -euo pipefail

../projects/calibration-updates-2026/scripts/assess_possum_1934s.sh \
  --manifest ../projects/calibration-updates-2026/manifests/sb_manifest_reffield_average.txt \
  --start-index 2 --end-index 2 \
  --beam-start 0 --beam-end 3
