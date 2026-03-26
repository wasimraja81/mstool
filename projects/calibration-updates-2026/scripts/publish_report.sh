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
MANIFEST_FILE="${SCRIPTS}/../manifests/manifest_ref_ws-4788.txt"
EXPERIMENT="baseline"

usage() { cat <<EOF
Usage: $(basename "$0") [options]

Syncs the assembled report package to the GitHub Pages repo.

Options:
  --manifest FILE              Manifest file (default: manifest_ref_ws-4788.txt)
  --experiment baseline|qcorr  Appends -qcorr to DATA_ROOT; drives PAGES_SUBDIR (default: baseline)
  -h, --help                   Show this help
EOF
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --manifest)
            MANIFEST_FILE="$2"
            shift 2
            ;;
        --experiment)
            EXPERIMENT="$2"
            shift 2
            ;;
        -h|--help)
            usage; exit 0
            ;;
        *)
            echo "ERROR: Unknown argument '$1'"
            exit 1
            ;;
    esac
done

# DATA_ROOT is read from LOCAL_BASE in the manifest; -qcorr suffix applied when --experiment qcorr.
DATA_ROOT="${HOME}/DATA/reffield-average"
if [[ -f "${MANIFEST_FILE}" ]]; then
    _local_base=$(awk -F'=' '/^LOCAL_BASE=/{gsub(/[[:space:]]/,"",$2); print $2}' "${MANIFEST_FILE}" | tail -1)
    [[ -n "${_local_base}" ]] && DATA_ROOT="${_local_base}"
fi
[[ "${EXPERIMENT}" == "qcorr" ]] && DATA_ROOT="${DATA_ROOT}-qcorr"
echo "INFO - DATA_ROOT: ${DATA_ROOT}"

PACKAGE_DIR="${DATA_ROOT}/final_mvp_share"
PAGES_CLONE="${HOME}/github-wasimraja81/askap-leakage-report"
PAGES_REMOTE="git@github.com:wasimraja81/askap-leakage-report.git"
PAGES_URL="https://wasimraja81.github.io/askap-leakage-report/"

# Derive publication subdirectory from DATA_ROOT basename.
# New convention:
#   assess_1934-ref_ws-4788        -> ref_ws-4788/baseline
#   assess_1934-ref_ws-4788-qcorr  -> ref_ws-4788/qcorr
#   assess_1934-ref_ws-5316        -> ref_ws-5316/baseline
# Legacy fallback (old naming):
#   reffield-average               -> ref_ws-4788/baseline
#   reffield-average-qcorr         -> ref_ws-4788/qcorr
_data_base="$(basename "${DATA_ROOT}")"
if [[ "${_data_base}" =~ ^assess_1934-ref_ws-([0-9]+)(-qcorr)?$ ]]; then
    _ref_ws_id="ref_ws-${BASH_REMATCH[1]}"
    if [[ -n "${BASH_REMATCH[2]}" ]]; then
        PAGES_SUBDIR="${_ref_ws_id}/qcorr"
    else
        PAGES_SUBDIR="${_ref_ws_id}/baseline"
    fi
elif [[ "${_data_base}" == "reffield-average-qcorr" ]]; then
    PAGES_SUBDIR="ref_ws-4788/qcorr"
elif [[ "${_data_base}" == "reffield-average" ]]; then
    PAGES_SUBDIR="ref_ws-4788/baseline"
else
    # Last-resort fallback — use basename as-is
    PAGES_SUBDIR="${_data_base}"
fi
echo "INFO - Publication subdir: '${PAGES_SUBDIR}'"
# Top-level cohort directory (part before the first '/'), e.g. ref_ws-5316
_ref_ws_id="${PAGES_SUBDIR%%/*}"

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
    cd "${PAGES_CLONE}"
    # Ensure develop branch exists; create from main if not
    if ! git show-ref --quiet refs/remotes/origin/develop; then
        git checkout -b develop
        git push -u origin develop
    else
        git checkout -b develop --track origin/develop
    fi
    # Add .nojekyll so GitHub Pages serves files/dirs with underscores correctly
    touch .nojekyll
    git add .nojekyll
    git commit -m "chore: add .nojekyll for GitHub Pages" || true
    git push origin develop
    cd -
else
    echo "Checking out develop and pulling latest ..."
    cd "${PAGES_CLONE}"
    git fetch origin
    # Switch to develop if not already on it
    git checkout develop 2>/dev/null || git checkout -b develop --track origin/develop
    git pull --ff-only origin develop
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

# ── Generate per-cohort index (ref_ws-NNNN/index.html) ───────────────────────
# Lists baseline/ and qcorr/ subdirs found inside the ref_ws-NNNN directory.
_REF_WS_DIR="${PAGES_CLONE}/${_ref_ws_id}"
_REF_WS_INDEX="${_REF_WS_DIR}/index.html"
echo "Updating cohort index: ${_REF_WS_INDEX}"
{
cat << 'RW_HEAD_EOF'
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>ASKAP Leakage Assessment Reports</title>
  <style>
    body { font-family: sans-serif; max-width: 600px; margin: 60px auto; padding: 0 20px; }
    h1   { font-size: 1.4em; }
    h2   { font-size: 1.1em; color: #555; }
    ul   { line-height: 2; }
    a.back { font-size: 0.9em; color: #888; }
  </style>
</head>
<body>
  <a class="back" href="../">&#8592; All cohorts</a>
RW_HEAD_EOF
printf '  <h1>ASKAP Leakage Assessment Reports</h1>\n'
printf '  <h2>%s</h2>\n' "${_ref_ws_id}"
printf '  <ul>\n'
find "${_REF_WS_DIR}" -mindepth 1 -maxdepth 1 -type d | sort | \
    while IFS= read -r _sub; do
        _name="$(basename "${_sub}")"
        printf '    <li><a href="./%s/">%s</a></li>\n' "${_name}" "${_name}"
    done
cat << 'RW_FOOT_EOF'
  </ul>
</body>
</html>
RW_FOOT_EOF
} > "${_REF_WS_INDEX}"

# ── Regenerate root landing page ──────────────────────────────────────────────
# Scans depth-1 for ref_ws-* directories; each links to its own cohort index.
LANDING="${PAGES_CLONE}/index.html"
echo "Updating landing page: ${LANDING}"
{
cat << 'HEAD_EOF'
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
  </style>
</head>
<body>
  <h1>ASKAP Leakage Assessment Reports</h1>
  <ul>
HEAD_EOF
find "${PAGES_CLONE}" -mindepth 1 -maxdepth 1 -type d -name "ref_ws-*" | sort | \
    while IFS= read -r _rw_dir; do
        _name="$(basename "${_rw_dir}")"
        printf '    <li><a href="./%s/">%s</a></li>\n' "${_name}" "${_name}"
    done
cat << 'FOOT_EOF'
  </ul>
</body>
</html>
FOOT_EOF
} > "${LANDING}"

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
