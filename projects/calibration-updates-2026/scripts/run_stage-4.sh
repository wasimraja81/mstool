#!/usr/bin/env bash
set -euo pipefail

../projects/calibration-updates-2026/scripts/copy_and_combine_assessment_results.sh \
  --manifest ../projects/calibration-updates-2026/manifests/sb_manifest_reffield_average.txt \
  --start-index 2 --end-index 2
