#!/usr/bin/env bash
# publish_report.sh
#
# Sync the assembled report package to the public GitHub Pages repo
# (wasimraja81/askap-leakage-report) so colleagues can view it at:
#
#   https://wasimraja81.github.io/askap-leakage-report/
#
# PREREQUISITES
# ─────────────────────────────────────────────────────────────────────────────
#  1. Run run_html_report.sh first — that builds the report AND assembles
#     the package into ${DATA_ROOT}/final_mvp_share/.
#
#  2. The GitHub repo must already exist and be public:
#     https://github.com/wasimraja81/askap-leakage-report
#
#  3. GitHub Pages must be enabled (Settings → Pages → Source: main branch / root).
#     Only needs to be done once after the first push.
#
# USAGE
# ─────────────────────────────────────────────────────────────────────────────
#   bash projects/calibration-updates-2026/scripts/publish_report.sh
#
# publish_report.sh pushes to the 'develop' branch of askap-leakage-report.
# When you are ready to go live, merge develop -> main on GitHub;
# GitHub Pages is configured to serve from main.
#
# On first run the repo is cloned into ${PAGES_CLONE}.
# On subsequent runs it pulls, syncs, commits and pushes in one step.
#
# ─────────────────────────────────────────────────────────────────────────────

set -euo pipefail

# ── Configuration ─────────────────────────────────────────────────────────────
SCRIPTS="$(python3 -c 'import os,sys; print(os.path.dirname(os.path.realpath(sys.argv[1])))' "$0")"
MANIFEST_FILE="${SCRIPTS}/../manifests/sb_manifest_reffield_average.txt"

# DATA_ROOT is read from LOCAL_BASE in the manifest.
# Hardcoded fallback (last used: reffield-average-qcorr):
DATA_ROOT="${HOME}/DATA/reffield-average-qcorr"
if [[ -f "${MANIFEST_FILE}" ]]; then
    _local_base=$(awk -F'=' '/^LOCAL_BASE=/{gsub(/[[:space:]]/,"",$2); print $2}' "${MANIFEST_FILE}" | tail -1)
    [[ -n "${_local_base}" ]] && DATA_ROOT="${_local_base}"
fi
echo "INFO - DATA_ROOT: ${DATA_ROOT}"

PACKAGE_DIR="${DATA_ROOT}/final_mvp_share"
PAGES_CLONE="${HOME}/github-wasimraja81/askap-leakage-report"
PAGES_REMOTE="git@github.com:wasimraja81/askap-leakage-report.git"
PAGES_URL="https://wasimraja81.github.io/askap-leakage-report/"

# Derive publication subdirectory from DATA_ROOT basename.
# Root index.html is ALWAYS the navigation landing page — reports go in subdirs.
# reffield-average        -> publishes to baseline/
# reffield-average-qcorr -> publishes to qcorr/
_data_base="$(basename "${DATA_ROOT}")"
if [[ "${_data_base}" == "reffield-average" ]]; then
    PAGES_SUBDIR="baseline"
else
    PAGES_SUBDIR="${_data_base#reffield-average-}"
    [[ "${PAGES_SUBDIR}" == "${_data_base}" ]] && PAGES_SUBDIR="${_data_base}"
fi
echo "INFO - Publication subdir: '${PAGES_SUBDIR}'"

# ── Sanity checks ─────────────────────────────────────────────────────────────
if [[ ! -f "${PACKAGE_DIR}/index.html" ]]; then
    echo "ERROR: ${PACKAGE_DIR}/index.html not found."
    echo "       Run run_html_report.sh (with --package) first."
    exit 1
fi

# ── Clone on first run ────────────────────────────────────────────────────────
if [[ ! -d "${PAGES_CLONE}/.git" ]]; then
    echo "First run: cloning ${PAGES_REMOTE} ..."
    mkdir -p "$(dirname "${PAGES_CLONE}")"
    git clone "${PAGES_REMOTE}" "${PAGES_CLONE}"

    # Add .nojekyll so GitHub Pages serves files/dirs with underscores correctly
    touch "${PAGES_CLONE}/.nojekyll"
    cd "${PAGES_CLONE}"
    git add .nojekyll
    git commit -m "chore: add .nojekyll for GitHub Pages"
    git branch -M main
    git push -u origin main
    cd -
else
    echo "Pulling latest from origin ..."
    cd "${PAGES_CLONE}"
    git pull --ff-only origin main
    cd -
fi

# ── Sync package → clone ──────────────────────────────────────────────────────
# Root index.html is permanently the navigation landing page — never overwritten
# by a report sync.  Each report lives in its own named subdirectory.
DEST_DIR="${PAGES_CLONE}/${PAGES_SUBDIR}"
echo "Syncing ${PACKAGE_DIR}/ → ${DEST_DIR}/ ..."
mkdir -p "${DEST_DIR}"
rsync -av --delete \
    --exclude=".git" \
    "${PACKAGE_DIR}/" "${DEST_DIR}/"

# Regenerate root landing page every publish so links stay up to date.
LANDING="${PAGES_CLONE}/index.html"
echo "Updating landing page: ${LANDING}"
cat > "${LANDING}" << 'LANDING_EOF'
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>ASKAP Leakage Assessment Reports</title>
  <style>
    body { font-family: sans-serif; max-width: 600px; margin: 60px auto; padding: 0 20px; }
    h1   { font-size: 1.4em; }
    ul   { line-height: 2; }
    .tag { font-size: 0.75em; background: #e8f4e8; border-radius: 3px;
           padding: 2px 6px; margin-left: 8px; }
    .new { background: #fff3cd; }
  </style>
</head>
<body>
  <h1>ASKAP Leakage Assessment Reports</h1>
  <ul>
    <li><a href="./baseline/">Baseline (no Q-correction)</a></li>
    <li><a href="./qcorr/">Q-corrected report</a><span class="tag new">new</span></li>
  </ul>
  <p style="font-size:0.85em; color:#666;">Q-correction removes residual X/Y gain
  amplitude imbalance (dQ) from the reference bandpass table. See the
  <a href="https://github.com/wasimraja81/mstool">mstool repo</a> for details.</p>
</body>
</html>
LANDING_EOF

# Ensure .nojekyll survives the rsync (package dir won't contain it)
touch "${PAGES_CLONE}/.nojekyll"

# ── Commit and push ───────────────────────────────────────────────────────────
cd "${PAGES_CLONE}"

if [[ -z "$(git status --porcelain)" ]]; then
    echo "Nothing changed since last publish — no commit needed."
else
    TIMESTAMP="$(date '+%Y-%m-%d %H:%M')"
    git add -A
    git commit -m "report: publish ${TIMESTAMP}"
    git push origin develop
    echo ""
    echo "Pushed to develop branch of askap-leakage-report."
    echo "To publish live: merge develop -> main on GitHub, then"
    echo "GitHub Pages will update at: ${PAGES_URL}"
fi

cd -
