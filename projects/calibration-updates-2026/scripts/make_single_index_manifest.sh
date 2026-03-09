#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEFAULT_INPUT_MANIFEST="${SCRIPT_DIR}/../manifests/sb_manifest_reffield_average.txt"

INDEX=""
INPUT_MANIFEST="${DEFAULT_INPUT_MANIFEST}"
OUTPUT_MANIFEST=""

usage() {
  cat <<EOF
Usage:
  make_single_index_manifest.sh --index N [--input FILE] [--output FILE]

Options:
  --index N        Required row index to keep (0-based)
  --input FILE     Source manifest (default: ${DEFAULT_INPUT_MANIFEST})
  --output FILE    Output manifest path (default: /tmp/mstool_manifest_idx<N>.txt)
  -h, --help       Show this help

Example:
  ./projects/calibration-updates-2026/scripts/make_single_index_manifest.sh --index 2
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --index)
      INDEX="$2"
      shift 2
      ;;
    --input)
      INPUT_MANIFEST="$2"
      shift 2
      ;;
    --output)
      OUTPUT_MANIFEST="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "ERROR: Unknown option '$1'"
      usage
      exit 1
      ;;
  esac
done

if [[ -z "${INDEX}" ]]; then
  echo "ERROR: --index is required"
  usage
  exit 1
fi

if [[ ! "${INDEX}" =~ ^[0-9]+$ ]]; then
  echo "ERROR: --index must be a non-negative integer"
  exit 1
fi

if [[ -z "${OUTPUT_MANIFEST}" ]]; then
  OUTPUT_MANIFEST="/tmp/mstool_manifest_idx${INDEX}.txt"
fi

[[ -f "${INPUT_MANIFEST}" ]] || { echo "ERROR: Input manifest not found: ${INPUT_MANIFEST}"; exit 1; }

awk -v idx="${INDEX}" '
  /^#/ { print; next }
  /^[A-Za-z_][A-Za-z0-9_]*=/ { print; next }
  $1==idx { print; found=1 }
  END {
    if (!found) {
      exit 42
    }
  }
' "${INPUT_MANIFEST}" > "${OUTPUT_MANIFEST}" || {
  rc=$?
  if [[ ${rc} -eq 42 ]]; then
    echo "ERROR: Index ${INDEX} not found in manifest rows: ${INPUT_MANIFEST}"
  else
    echo "ERROR: Failed to generate output manifest"
  fi
  exit ${rc}
}

echo "Wrote single-index manifest: ${OUTPUT_MANIFEST}"
