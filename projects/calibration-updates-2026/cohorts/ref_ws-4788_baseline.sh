#!/usr/bin/env bash
# =============================================================================
# Cohort:     ref_ws-4788  (ODC_WEIGHT_ID=5231, indices 0–49)
# Experiment: baseline  (no Q-corrections → produces correction CSV)
# Manifest:   manifests/manifest_ref_ws-4788.txt
# =============================================================================
# WORKFLOW
#   Run each stage in order.  Stages 1 and 2 submit SLURM jobs — wait for
#   the HPC jobs to complete before continuing to stage 3.
#
#   bash cohorts/ref_ws-4788_baseline.sh stage1   # submit ref-field jobs
#   # ... wait for SLURM completion ...
#   bash cohorts/ref_ws-4788_baseline.sh stage2   # submit 1934 calib jobs
#   # ... wait for SLURM completion ...
#   bash cohorts/ref_ws-4788_baseline.sh stage3   # assess (runs on HPC)
#   bash cohorts/ref_ws-4788_baseline.sh stage4   # rsync + combine locally
#   bash cohorts/ref_ws-4788_baseline.sh report   # build HTML report
#   bash cohorts/ref_ws-4788_baseline.sh publish  # push to GitHub Pages
# =============================================================================
set -euo pipefail

COHORT_DIR="$(cd "$(dirname "$0")" && pwd)"
SCRIPTS="${COHORT_DIR}/../scripts"
MANIFESTS="${COHORT_DIR}/../manifests"
MANIFEST="${MANIFESTS}/manifest_ref_ws-4788.txt"
EXPERIMENT="baseline"
START_INDEX="0"
END_INDEX="49"

stage1() {
    "${SCRIPTS}"/run_stage-1.sh \
        --manifest      "${MANIFEST}" \
        --start-index   "${START_INDEX}" \
        --end-index     "${END_INDEX}" \
        --apply-q-corrections false
}

stage2() {
    "${SCRIPTS}"/run_stage-2.sh \
        --manifest      "${MANIFEST}" \
        --start-index   "${START_INDEX}" \
        --end-index     "${END_INDEX}"
}

stage3() {
    "${SCRIPTS}"/run_stage-3.sh \
        --manifest      "${MANIFEST}" \
        --start-index   "${START_INDEX}" \
        --end-index     "${END_INDEX}" \
        --beam-start    0 \
        --beam-end      35 \
        --experiment    "${EXPERIMENT}"
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
case "${1:-all}" in
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
        echo "Usage: $0 {stage1|stage2|stage3|stage4|report|publish|all}"
        exit 1
        ;;
esac
