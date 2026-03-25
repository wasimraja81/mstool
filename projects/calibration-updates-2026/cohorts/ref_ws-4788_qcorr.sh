#!/usr/bin/env bash
# =============================================================================
# Cohort:     ref_ws-4788  (ODC_WEIGHT_ID=5231, indices 0–49)
# Experiment: qcorr  (Q-corrections applied → assesses residual leakage)
# Manifest:   manifests/manifest_ref_ws-4788.txt
# Prereq:     run ref_ws-4788_baseline first to generate the correction CSV
# =============================================================================
# WORKFLOW
#   bash cohorts/ref_ws-4788_qcorr.sh stage1   # submit ref-field jobs (Q-corr)
#   # ... wait for SLURM completion ...
#   bash cohorts/ref_ws-4788_qcorr.sh stage2   # submit 1934 calib jobs
#   # ... wait for SLURM completion ...
#   bash cohorts/ref_ws-4788_qcorr.sh stage3   # assess (uses qcorr HPC path)
#   bash cohorts/ref_ws-4788_qcorr.sh stage4   # rsync + combine to LOCAL-qcorr
#   bash cohorts/ref_ws-4788_qcorr.sh report   # build HTML report (qcorr data)
#   bash cohorts/ref_ws-4788_qcorr.sh publish  # push qcorr/ to GitHub Pages
# =============================================================================
set -euo pipefail

COHORT_DIR="$(cd "$(dirname "$0")" && pwd)"
SCRIPTS="${COHORT_DIR}/../scripts"
MANIFESTS="${COHORT_DIR}/../manifests"
MANIFEST="${MANIFESTS}/manifest_ref_ws-4788.txt"
EXPERIMENT="qcorr"
START_INDEX="0"
END_INDEX="49"

# Q-correction parameters — update Q_CORR_CSV when a new table is derived.
Q_CORR_CSV="/askapbuffer/payne/raj030/askap-calibration-updates/dq_du_correction_factors.csv"
Q_CORR_VARIANT="bpcal"

stage1() {
    "${SCRIPTS}"/run_stage-1.sh \
        --manifest              "${MANIFEST}" \
        --start-index           "${START_INDEX}" \
        --end-index             "${END_INDEX}" \
        --apply-q-corrections   true \
        --q-corr-csv            "${Q_CORR_CSV}" \
        --q-corr-variant        "${Q_CORR_VARIANT}"
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
