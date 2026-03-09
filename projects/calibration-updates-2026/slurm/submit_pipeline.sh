#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../../.." && pwd)"

REF_SCRIPT="${SCRIPT_DIR}/start_refField.slurm"
SCI_SCRIPT="${SCRIPT_DIR}/start_1934s.slurm"
MANIFEST_DEFAULT="${SCRIPT_DIR}/../manifests/sb_manifest_reffield_average.txt"

MANIFEST_FILE="${MANIFEST_DEFAULT}"
START_INDEX=""
END_INDEX=""
DRY_RUN=0
STAGE="ref"

usage() {
  cat <<EOF
Usage:
  submit_pipeline.sh [options]

Options:
  --manifest PATH      Manifest file path (default: ${MANIFEST_DEFAULT})
  --start-index N      Optional start index (0-based)
  --end-index N        Optional end index (0-based)
  --stage NAME         Stage to submit: ref | 1934 (default: ref)
  --dry-run            Print sbatch commands without submitting
  -h, --help           Show this help

Examples:
  ./projects/calibration-updates-2026/slurm/submit_pipeline.sh --stage ref
  ./projects/calibration-updates-2026/slurm/submit_pipeline.sh --stage 1934
  ./projects/calibration-updates-2026/slurm/submit_pipeline.sh --start-index 19 --end-index 19
  ./projects/calibration-updates-2026/slurm/submit_pipeline.sh --manifest projects/calibration-updates-2026/manifests/sb_manifest_reffield_average.txt
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --manifest)
      MANIFEST_FILE="$2"
      shift 2
      ;;
    --start-index)
      START_INDEX="$2"
      shift 2
      ;;
    --end-index)
      END_INDEX="$2"
      shift 2
      ;;
    --stage)
      STAGE="$2"
      shift 2
      ;;
    --dry-run)
      DRY_RUN=1
      shift
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

if [[ ! -f "${MANIFEST_FILE}" ]]; then
  if [[ -f "${REPO_ROOT}/${MANIFEST_FILE}" ]]; then
    MANIFEST_FILE="${REPO_ROOT}/${MANIFEST_FILE}"
  fi
fi

[[ -f "${MANIFEST_FILE}" ]] || { echo "ERROR: Manifest not found: ${MANIFEST_FILE}"; exit 1; }
[[ -f "${REF_SCRIPT}" ]] || { echo "ERROR: Missing script: ${REF_SCRIPT}"; exit 1; }
[[ -f "${SCI_SCRIPT}" ]] || { echo "ERROR: Missing script: ${SCI_SCRIPT}"; exit 1; }

ref_cmd=(sbatch --parsable "${REF_SCRIPT}" --manifest "${MANIFEST_FILE}")
sci_cmd=(sbatch --parsable "${SCI_SCRIPT}" --manifest "${MANIFEST_FILE}")

if [[ -n "${START_INDEX}" ]]; then
  ref_cmd+=(--start-index "${START_INDEX}")
  sci_cmd+=(--start-index "${START_INDEX}")
fi
if [[ -n "${END_INDEX}" ]]; then
  ref_cmd+=(--end-index "${END_INDEX}")
  sci_cmd+=(--end-index "${END_INDEX}")
fi

echo "Repo root   : ${REPO_ROOT}"
echo "Manifest    : ${MANIFEST_FILE}"

case "${STAGE}" in
  ref)
    selected_cmd=("${ref_cmd[@]}")
    selected_desc="refField stage"
    ;;
  1934)
    selected_cmd=("${sci_cmd[@]}")
    selected_desc="1934 stage"
    ;;
  *)
    echo "ERROR: Invalid --stage '${STAGE}'. Use 'ref' or '1934'."
    exit 1
    ;;
esac

echo "Stage       : ${selected_desc}"
echo "Command     : ${selected_cmd[*]}"
echo "NOTE        : This helper intentionally does NOT chain stage-2 to stage-1 parent job completion."
echo "              processASKAP launches child pipeline jobs; submit stage 1934 only after those complete."

if [[ ${DRY_RUN} -eq 1 ]]; then
  exit 0
fi

submitted_jid="$("${selected_cmd[@]}")"
echo "Submitted ${selected_desc}: ${submitted_jid}"
