#!/usr/bin/env bash
# =============================================================================
# Cohort:     ref_ws-5815  (ODC_WEIGHT_ID=5845, midband, indices 0–15)
# Experiment: baseline  test1 (chanMedian), re-run with
#             askapsoft axa-4203-30d8a0a and askappipeline 2.27.1
# Manifest:   manifests/manifest_ref_ws-5815-test1-chanMedian-askapsoft-axa-4203-30d8a0a.txt
# Templates:  slurm/RF-midband-spectral-test1-chanMedian-askapsoft-axa-4203-30d8a0a.sh (stage 1)
#             slurm/run_1934Field_midband-askapsoft-axa-4203-30d8a0a.sh (stage 2)
# Isolation:  HPC_BASE_DIR, LOCAL_BASE and the gh-pages folder are all new
#             (see manifest), so older test1 products are untouched.
# =============================================================================
# WORKFLOW
#   Run each stage in order.  Stages 1 and 2 submit SLURM jobs — wait for
#   the HPC jobs to complete before continuing to the next stage.
#
#   bash cohorts/ref_ws-5815_test1-chanMedian-askapsoft-axa-4203-30d8a0a.sh stage1   # submit ref-field jobs
#   # ... wait for SLURM completion ...
#   bash cohorts/ref_ws-5815_test1-chanMedian-askapsoft-axa-4203-30d8a0a.sh stage2   # submit 1934 calib jobs
#   # ... wait for SLURM completion ...
#   bash cohorts/ref_ws-5815_test1-chanMedian-askapsoft-axa-4203-30d8a0a.sh stage3   # assess (runs on HPC)
#   bash cohorts/ref_ws-5815_test1-chanMedian-askapsoft-axa-4203-30d8a0a.sh stage4   # rsync + combine locally
#   bash cohorts/ref_ws-5815_test1-chanMedian-askapsoft-axa-4203-30d8a0a.sh report   # build HTML report
#   bash cohorts/ref_ws-5815_test1-chanMedian-askapsoft-axa-4203-30d8a0a.sh publish  # push to GitHub Pages (develop)
# =============================================================================
set -euo pipefail

COHORT_DIR="$(cd "$(dirname "$0")" && pwd)"
SCRIPTS="${COHORT_DIR}/../scripts"
MANIFESTS="${COHORT_DIR}/../manifests"
SLURM="${COHORT_DIR}/../slurm"
LABEL="askapsoft-axa-4203-30d8a0a"
MANIFEST="${MANIFESTS}/manifest_ref_ws-5815-test1-chanMedian-${LABEL}.txt"
REF_TEMPLATE="${SLURM}/RF-midband-spectral-test1-chanMedian-${LABEL}.sh"
SCI_TEMPLATE="${SLURM}/run_1934Field_midband-${LABEL}.sh"
MS_TAG="Bandpass_square_6x6_1272MHz_0.9_1MHz"
EXPERIMENT="baseline"
START_INDEX="0"
END_INDEX="15"

stage1() {
    "${SCRIPTS}"/run_stage-1.sh \
        --manifest      "${MANIFEST}" \
        --start-index   "${START_INDEX}" \
        --end-index     "${END_INDEX}" \
        --experiment    "${EXPERIMENT}" \
        --template      "${REF_TEMPLATE}" \
        ${DRY_RUN_ARGS[@]+"${DRY_RUN_ARGS[@]}"}
}

stage2() {
    "${SCRIPTS}"/run_stage-2.sh \
        --manifest      "${MANIFEST}" \
        --start-index   "${START_INDEX}" \
        --end-index     "${END_INDEX}" \
        --experiment    "${EXPERIMENT}" \
        --template      "${SCI_TEMPLATE}" \
        ${DRY_RUN_ARGS[@]+"${DRY_RUN_ARGS[@]}"}
}

stage3() {
    "${SCRIPTS}"/run_stage-3.sh \
        --manifest      "${MANIFEST}" \
        --start-index   "${START_INDEX}" \
        --end-index     "${END_INDEX}" \
        --beam-start    0 \
        --beam-end      35 \
        --experiment    "${EXPERIMENT}" \
        --ms-tag        "${MS_TAG}"
}

stage4() {
    "${SCRIPTS}"/run_stage-4.sh \
        --manifest      "${MANIFEST}" \
        --start-index   "${START_INDEX}" \
        --end-index     "${END_INDEX}" \
        --experiment    "${EXPERIMENT}" \
        --copy-metadata
}

report() {
    "${SCRIPTS}"/run_html_report.sh \
        --manifest      "${MANIFEST}" \
        --start-index   "${START_INDEX}" \
        --end-index     "${END_INDEX}" \
        --experiment    "${EXPERIMENT}"
}

publish() {
    "${SCRIPTS}"/publish_report.sh \
        --manifest      "${MANIFEST}" \
        --experiment    "${EXPERIMENT}"
}

# ── Dispatch ──────────────────────────────────────────────────────────────────
usage() {
    echo "Usage: $0 {stage1|stage2|stage3|stage4|report|publish|all} [--dry-run]"
    echo "  --dry-run  stage1/stage2 only: print the sbatch command, do not submit"
    echo "  'all' must be given explicitly; no argument prints this help."
}

STAGE="${1:-}"
[[ $# -gt 0 ]] && shift
DRY_RUN_ARGS=()
for _arg in "$@"; do
    case "${_arg}" in
        --dry-run) DRY_RUN_ARGS=(--dry-run) ;;
        *) echo "ERROR: Unknown argument '${_arg}'"; usage; exit 1 ;;
    esac
done
if [[ ${#DRY_RUN_ARGS[@]} -gt 0 && "${STAGE}" != "stage1" && "${STAGE}" != "stage2" ]]; then
    echo "ERROR: --dry-run is only supported for stage1 and stage2."
    exit 1
fi

case "${STAGE}" in
    stage1)  stage1  ;;
    stage2)  stage2  ;;
    stage3)  stage3  ;;
    stage4)  stage4  ;;
    report)  report  ;;
    publish) publish ;;
    all)
        echo "INFO: Running all stages in sequence."
        echo "      For HPC workflows, stages 1 and 2 submit SLURM jobs."
        echo "      The script does NOT wait — ensure jobs complete before stage 3."
        stage1; stage2; stage3; stage4; report; publish
        ;;
    *)
        usage
        exit 1
        ;;
esac
