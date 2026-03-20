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
DATA_ROOT="${HOME}/DATA/reffield-average"
PACKAGE_DIR="${DATA_ROOT}/final_mvp_share"
PAGES_CLONE="${HOME}/github-wasimraja81/askap-leakage-report"
PAGES_REMOTE="git@github.com:wasimraja81/askap-leakage-report.git"
PAGES_URL="https://wasimraja81.github.io/askap-leakage-report/"

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
echo "Syncing ${PACKAGE_DIR}/ → ${PAGES_CLONE}/ ..."
rsync -av --delete \
    --exclude=".git" \
    "${PACKAGE_DIR}/" "${PAGES_CLONE}/"

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
