#!/usr/bin/env bash
set -euo pipefail

# -----------------------------
# User-configurable settings
# -----------------------------
REMOTE="raj030@setonix-dm03.pawsey.org.au"
REMOTE_BASE_ROOT="/scratch/askaprt/raj030/tickets/axa-3649-component-models/assess_1934-2026"
ODC_WEIGHT_ID="5229"
REMOTE_BASE="${REMOTE_BASE_ROOT}/ODC-${ODC_WEIGHT_ID}"
LOCAL_PARENT="${HOME}/DATA"
LOCAL_NAME="reffield-average"
LOCAL_BASE="${LOCAL_PARENT}/${LOCAL_NAME}"
LOCAL_BASE_EXPLICIT=0
DRY_RUN=0
OVERRIDE_SB_REF=""
OVERRIDE_SB_1934=""
OVERRIDE_SB_HOLO=""
OVERRIDE_SB_TARGET_1934=""
MANIFEST_FILE=""

normalize_tag() {
  local value="$1"
  local prefix="$2"
  if [[ -z "${value}" ]]; then
    echo ""
    return
  fi
  if [[ "${value}" =~ ^[0-9]+$ ]]; then
    echo "${prefix}${value}"
  elif [[ "${value}" == ${prefix}* ]]; then
    echo "${value}"
  else
    echo "${value}"
  fi
}

normalize_odc_tag() {
  local value="$1"
  if [[ -z "${value}" ]]; then
    echo ""
    return
  fi
  if [[ "${value}" =~ ^[0-9]+$ ]]; then
    echo "ODC-${value}"
  elif [[ "${value}" =~ ^ODC-[0-9]+$ ]]; then
    echo "${value}"
  else
    echo "${value}"
  fi
}

resolve_remote_base_from_odc() {
  if [[ -z "${ODC_WEIGHT_ID}" ]]; then
    return
  fi

  local odc_tag
  odc_tag="$(normalize_odc_tag "${ODC_WEIGHT_ID}")"
  if [[ ! "${odc_tag}" =~ ^ODC-[0-9]+$ ]]; then
    echo "ERROR: Invalid ODC weight ID '${ODC_WEIGHT_ID}'. Expected numeric ID (e.g. 5231) or ODC-NNNN."
    exit 1
  fi

  if [[ -n "${REMOTE_BASE_ROOT}" ]]; then
    REMOTE_BASE="${REMOTE_BASE_ROOT%/}/${odc_tag}"
  elif [[ "${REMOTE_BASE}" =~ ^(.*/)(ODC-[0-9]+)$ ]]; then
    REMOTE_BASE="${BASH_REMATCH[1]}${odc_tag}"
  else
    REMOTE_BASE="${REMOTE_BASE%/}/${odc_tag}"
  fi
}

resolve_remote_base_for_odc() {
  local odc_value="$1"
  local effective_odc="${odc_value:-${ODC_WEIGHT_ID}}"
  local odc_tag

  if [[ -z "${effective_odc}" ]]; then
    echo "${REMOTE_BASE}"
    return
  fi

  odc_tag="$(normalize_odc_tag "${effective_odc}")"
  if [[ ! "${odc_tag}" =~ ^ODC-[0-9]+$ ]]; then
    echo "ERROR: Invalid ODC weight ID '${effective_odc}'. Expected numeric ID (e.g. 5231) or ODC-NNNN." >&2
    return 1
  fi

  if [[ -n "${REMOTE_BASE_ROOT}" ]]; then
    echo "${REMOTE_BASE_ROOT%/}/${odc_tag}"
  elif [[ "${REMOTE_BASE}" =~ ^(.*/)(ODC-[0-9]+)$ ]]; then
    echo "${BASH_REMATCH[1]}${odc_tag}"
  else
    echo "${REMOTE_BASE%/}/${odc_tag}"
  fi
}

# Auto-detect repo root from script location:
# script is expected at <repo>/scripts/copy_and_combine_assessment_results.sh
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
COMBINE_SCRIPT="${REPO_ROOT}/mstool/bin/combine_beam_outputs.py"

# Remote subpaths to copy are constructed from SB IDs + shared naming pattern.
# Update these values for each run.
SOURCE_SB_REF_IDS=(81082 81083)
SOURCE_SB_1934_ID="77045"
SOURCE_SB_HOLO_ID="76554"
SOURCE_SB_TARGET_1934_ID="81089"
SOURCE_AMP_STRATEGY="multiply-insituPreflags"

SUBPATHS=()
SUBPATH_REMOTE_BASES=()

build_subpaths() {
  SUBPATHS=()
  SUBPATH_REMOTE_BASES=()
  for sb_ref_id in "${SOURCE_SB_REF_IDS[@]}"; do
    SUBPATHS+=(
      "SB_REF-${sb_ref_id}_SB_1934-${SOURCE_SB_1934_ID}_SB_HOLO-${SOURCE_SB_HOLO_ID}_AMP_STRATEGY-${SOURCE_AMP_STRATEGY}/1934-processing-SB-${SOURCE_SB_TARGET_1934_ID}/assessment_results/"
    )
    SUBPATH_REMOTE_BASES+=("${REMOTE_BASE}")
  done
}

build_subpaths_from_manifest() {
  local manifest_path="$1"

  [[ -f "${manifest_path}" ]] || { echo "ERROR: --manifest file not found: ${manifest_path}"; exit 1; }

  SUBPATHS=()
  SUBPATH_REMOTE_BASES=()
  local line_no=0
  while IFS= read -r raw_line || [[ -n "${raw_line}" ]]; do
    line_no=$((line_no + 1))

    # Remove comments and trim whitespace
    local line="${raw_line%%#*}"
    line="$(echo "${line}" | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//')"
    [[ -z "${line}" ]] && continue

    # Manifest-level config directives (KEY=VALUE), e.g.
    # REMOTE=raj030@setonix-dm03.pawsey.org.au
    # REMOTE_BASE=/scratch/.../ODC-5229
    # REMOTE_BASE_ROOT=/scratch/.../assess_1934-2026
    # ODC_WEIGHT_ID=5231
    # LOCAL_BASE=/Users/me/DATA/reffield-average
    # AMP_STRATEGY=multiply-insituPreflags
    if [[ "${line}" =~ ^([A-Za-z_][A-Za-z0-9_]*)=(.+)$ ]]; then
      local cfg_key="${BASH_REMATCH[1]}"
      local cfg_val="${BASH_REMATCH[2]}"
      cfg_val="$(echo "${cfg_val}" | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//')"

      case "${cfg_key}" in
        REMOTE)
          REMOTE="${cfg_val}"
          ;;
        REMOTE_BASE)
          REMOTE_BASE="${cfg_val}"
          ;;
        REMOTE_BASE_ROOT)
          REMOTE_BASE_ROOT="${cfg_val}"
          ;;
        ODC_WEIGHT_ID|ODC|WEIGHT_ID)
          ODC_WEIGHT_ID="${cfg_val}"
          ;;
        LOCAL_BASE)
          LOCAL_BASE="${cfg_val}"
          LOCAL_BASE_EXPLICIT=1
          ;;
        LOCAL_PARENT)
          LOCAL_PARENT="${cfg_val}"
          ;;
        LOCAL_NAME)
          LOCAL_NAME="${cfg_val}"
          ;;
        AMP_STRATEGY)
          SOURCE_AMP_STRATEGY="${cfg_val}"
          ;;
        *)
          echo "WARNING: Unknown manifest config key '${cfg_key}' on line ${line_no}; ignoring"
          ;;
      esac
      continue
    fi

    # Accept comma- or whitespace-separated fields for SBID rows
    line="${line//,/ }"
    local col1="" col2="" col3="" col4="" col5="" col6="" extra=""
    read -r col1 col2 col3 col4 col5 col6 extra <<< "${line}"

    # Skip header line if present
    local col1_lc
    col1_lc="$(echo "${col1}" | tr '[:upper:]' '[:lower:]')"
    if [[ "${col1_lc}" == "sb_ref" || "${col1_lc}" == "sbref" ]]; then
      continue
    fi

    if [[ -z "${col1}" || -z "${col2}" || -z "${col3}" || -z "${col4}" ]]; then
      echo "WARNING: Skipping manifest line ${line_no}: expected 4 to 6 columns (sb_ref sb_1934 sb_holo sb_target_1934 [odc_weight_id] [amp_strategy])"
      continue
    fi

    local sb_ref_tag sb_1934_tag sb_holo_tag sb_target_tag amp_strategy row_odc_weight row_remote_base
    sb_ref_tag="$(normalize_tag "${col1}" "SB_REF-")"
    sb_1934_tag="$(normalize_tag "${col2}" "SB_1934-")"
    sb_holo_tag="$(normalize_tag "${col3}" "SB_HOLO-")"
    sb_target_tag="$(normalize_tag "${col4}" "SB_TARGET_1934-")"
    amp_strategy="${SOURCE_AMP_STRATEGY}"
    row_odc_weight=""

    if [[ -n "${col5}" ]]; then
      if [[ "${col5}" =~ ^(ODC-)?[0-9]+$ ]]; then
        row_odc_weight="${col5}"
      else
        amp_strategy="${col5}"
      fi
    fi

    if [[ -n "${col6}" ]]; then
      if [[ "${col6}" =~ ^(ODC-)?[0-9]+$ ]]; then
        if [[ -n "${row_odc_weight}" ]]; then
          echo "WARNING: Skipping manifest line ${line_no}: multiple ODC values provided ('${col5}', '${col6}')"
          continue
        fi
        row_odc_weight="${col6}"
      elif [[ "${amp_strategy}" != "${SOURCE_AMP_STRATEGY}" ]]; then
        echo "WARNING: Skipping manifest line ${line_no}: multiple amp_strategy values provided ('${col5}', '${col6}')"
        continue
      else
        amp_strategy="${col6}"
      fi
    fi

    if [[ -n "${extra}" ]]; then
      echo "WARNING: Skipping manifest line ${line_no}: too many columns"
      continue
    fi

    if [[ ! "${sb_ref_tag}" =~ ^SB_REF-([0-9]+)$ ]]; then
      echo "WARNING: Skipping manifest line ${line_no}: invalid SB_REF value '${col1}'"
      continue
    fi
    local sb_ref_id="${BASH_REMATCH[1]}"

    if [[ ! "${sb_1934_tag}" =~ ^SB_1934-([0-9]+)$ ]]; then
      echo "WARNING: Skipping manifest line ${line_no}: invalid SB_1934 value '${col2}'"
      continue
    fi
    local sb_1934_id="${BASH_REMATCH[1]}"

    if [[ ! "${sb_holo_tag}" =~ ^SB_HOLO-([0-9]+)$ ]]; then
      echo "WARNING: Skipping manifest line ${line_no}: invalid SB_HOLO value '${col3}'"
      continue
    fi
    local sb_holo_id="${BASH_REMATCH[1]}"

    if [[ ! "${sb_target_tag}" =~ ^SB_TARGET_1934-([0-9]+)$ ]]; then
      echo "WARNING: Skipping manifest line ${line_no}: invalid SB_TARGET_1934 value '${col4}'"
      continue
    fi
    local sb_target_id="${BASH_REMATCH[1]}"

    SUBPATHS+=(
      "SB_REF-${sb_ref_id}_SB_1934-${sb_1934_id}_SB_HOLO-${sb_holo_id}_AMP_STRATEGY-${amp_strategy}/1934-processing-SB-${sb_target_id}/assessment_results/"
    )
    row_remote_base="$(resolve_remote_base_for_odc "${row_odc_weight}")" || exit 1
    SUBPATH_REMOTE_BASES+=("${row_remote_base}")
  done < "${manifest_path}"

  if [[ ${#SUBPATHS[@]} -eq 0 ]]; then
    echo "ERROR: No valid SUBPATHS generated from manifest: ${manifest_path}"
    exit 1
  fi
}

usage() {
  cat << 'EOF'
Usage:
  copy_and_combine_assessment_results.sh [options]

Options:
  --dry-run                 Show what would be copied/processed; do not copy or run combine.
  --remote USER@HOST        Remote SSH target (default: raj030@setonix-dm03.pawsey.org.au).
  --odc-weight-id ID        ODC weight ID (e.g. 5231 or ODC-5231).
  --remote-base PATH        Remote base directory containing SB_REF-* paths.
  --remote-base-root PATH   Remote base root; REMOTE_BASE becomes <root>/ODC-<ID> when ODC is set.
  --local-base PATH         Full local destination path (overrides parent/name options).
  --local-parent PATH       Parent directory for local copy destination.
  --local-name NAME         Directory name under --local-parent.
  --manifest FILE           ASCII file listing SBID combinations and optional config directives.
  --sb-ref TAG              Override SB_REF tag passed to combine script.
  --sb-1934 TAG             Override SB_1934 tag passed to combine script.
  --sb-holo TAG             Override SB_HOLO tag passed to combine script.
  --sb-target-1934 TAG      Override SB_TARGET_1934 tag passed to combine script.
  -h, --help                Show this help.

Examples:
  ./scripts/copy_and_combine_assessment_results.sh
  ./scripts/copy_and_combine_assessment_results.sh --dry-run
  ./scripts/copy_and_combine_assessment_results.sh --manifest sbids.txt
  ./scripts/copy_and_combine_assessment_results.sh --local-base /data/results/assess_1934
  ./scripts/copy_and_combine_assessment_results.sh --local-parent /data/results --local-name my_assessment_run

Manifest format:
  - Comments begin with '#'
  - Optional config directives: KEY=VALUE
      REMOTE=...
      REMOTE_BASE=...
      REMOTE_BASE_ROOT=...
      ODC_WEIGHT_ID=...   (aliases: ODC, WEIGHT_ID)
      LOCAL_BASE=...   (or LOCAL_PARENT/LOCAL_NAME)
      AMP_STRATEGY=...
  - SB rows (space or comma separated):
      sb_ref sb_1934 sb_holo sb_target_1934 [odc_weight_id] [amp_strategy]
      (optional odc_weight_id and amp_strategy may be provided in either order)
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run)
      DRY_RUN=1
      shift
      ;;
    --remote)
      [[ $# -ge 2 ]] || { echo "ERROR: --remote requires a value"; exit 1; }
      REMOTE="$2"
      shift 2
      ;;
    --odc-weight-id|--odc)
      [[ $# -ge 2 ]] || { echo "ERROR: $1 requires a value"; exit 1; }
      ODC_WEIGHT_ID="$2"
      shift 2
      ;;
    --remote-base)
      [[ $# -ge 2 ]] || { echo "ERROR: --remote-base requires a value"; exit 1; }
      REMOTE_BASE="$2"
      shift 2
      ;;
    --remote-base-root)
      [[ $# -ge 2 ]] || { echo "ERROR: --remote-base-root requires a value"; exit 1; }
      REMOTE_BASE_ROOT="$2"
      shift 2
      ;;
    --local-base)
      [[ $# -ge 2 ]] || { echo "ERROR: --local-base requires a value"; exit 1; }
      LOCAL_BASE="$2"
      LOCAL_BASE_EXPLICIT=1
      shift 2
      ;;
    --local-parent)
      [[ $# -ge 2 ]] || { echo "ERROR: --local-parent requires a value"; exit 1; }
      LOCAL_PARENT="$2"
      shift 2
      ;;
    --local-name)
      [[ $# -ge 2 ]] || { echo "ERROR: --local-name requires a value"; exit 1; }
      LOCAL_NAME="$2"
      shift 2
      ;;
    --manifest)
      [[ $# -ge 2 ]] || { echo "ERROR: --manifest requires a value"; exit 1; }
      MANIFEST_FILE="$2"
      shift 2
      ;;
    --sb-ref)
      [[ $# -ge 2 ]] || { echo "ERROR: --sb-ref requires a value"; exit 1; }
      OVERRIDE_SB_REF="$2"
      shift 2
      ;;
    --sb-1934)
      [[ $# -ge 2 ]] || { echo "ERROR: --sb-1934 requires a value"; exit 1; }
      OVERRIDE_SB_1934="$2"
      shift 2
      ;;
    --sb-holo)
      [[ $# -ge 2 ]] || { echo "ERROR: --sb-holo requires a value"; exit 1; }
      OVERRIDE_SB_HOLO="$2"
      shift 2
      ;;
    --sb-target-1934)
      [[ $# -ge 2 ]] || { echo "ERROR: --sb-target-1934 requires a value"; exit 1; }
      OVERRIDE_SB_TARGET_1934="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "ERROR: Unknown option: $1"
      usage
      exit 1
      ;;
  esac
done

# If --local-base is not explicitly set, compose from parent + name
if [[ ${LOCAL_BASE_EXPLICIT} -eq 0 ]]; then
  LOCAL_BASE="${LOCAL_PARENT}/${LOCAL_NAME}"
fi

OVERRIDE_SB_REF="$(normalize_tag "${OVERRIDE_SB_REF}" "SB_REF-")"
OVERRIDE_SB_1934="$(normalize_tag "${OVERRIDE_SB_1934}" "SB_1934-")"
OVERRIDE_SB_HOLO="$(normalize_tag "${OVERRIDE_SB_HOLO}" "SB_HOLO-")"
OVERRIDE_SB_TARGET_1934="$(normalize_tag "${OVERRIDE_SB_TARGET_1934}" "SB_TARGET_1934-")"

resolve_remote_base_from_odc

if [[ -n "${MANIFEST_FILE}" ]]; then
  build_subpaths_from_manifest "${MANIFEST_FILE}"
else
  # If SB overrides are provided, use them to drive copy source path construction too.
  if [[ "${OVERRIDE_SB_REF}" =~ ^SB_REF-([0-9]+)$ ]]; then
    SOURCE_SB_REF_IDS=("${BASH_REMATCH[1]}")
  fi
  if [[ "${OVERRIDE_SB_1934}" =~ ^SB_1934-([0-9]+)$ ]]; then
    SOURCE_SB_1934_ID="${BASH_REMATCH[1]}"
  fi
  if [[ "${OVERRIDE_SB_HOLO}" =~ ^SB_HOLO-([0-9]+)$ ]]; then
    SOURCE_SB_HOLO_ID="${BASH_REMATCH[1]}"
  fi
  if [[ "${OVERRIDE_SB_TARGET_1934}" =~ ^SB_TARGET_1934-([0-9]+)$ ]]; then
    SOURCE_SB_TARGET_1934_ID="${BASH_REMATCH[1]}"
  fi

  build_subpaths
fi

echo "==> Configuration"
echo "  Remote host/base: ${REMOTE}:${REMOTE_BASE}"
echo "  ODC weight ID: ${ODC_WEIGHT_ID:-none}"
echo "  Local destination: ${LOCAL_BASE}"
echo "  Dry run: ${DRY_RUN}"
echo "  Manifest: ${MANIFEST_FILE:-none}"
echo "  Tag overrides: sb_ref=${OVERRIDE_SB_REF:-auto}, sb_1934=${OVERRIDE_SB_1934:-auto}, sb_holo=${OVERRIDE_SB_HOLO:-auto}, sb_target_1934=${OVERRIDE_SB_TARGET_1934:-auto}"
if [[ -n "${MANIFEST_FILE}" ]]; then
  echo "  Source IDs: driven by manifest rows (including per-row ODC if provided)"
else
  echo "  Source IDs: sb_ref_ids=${SOURCE_SB_REF_IDS[*]}, sb_1934=${SOURCE_SB_1934_ID}, sb_holo=${SOURCE_SB_HOLO_ID}, sb_target_1934=${SOURCE_SB_TARGET_1934_ID}"
fi
echo "  Generated SUBPATH count: ${#SUBPATHS[@]}"

echo "==> Checking prerequisites"
command -v tar >/dev/null 2>&1 || { echo "ERROR: tar not found"; exit 1; }
command -v python >/dev/null 2>&1 || { echo "ERROR: python not found"; exit 1; }
command -v ssh >/dev/null 2>&1 || { echo "ERROR: ssh not found"; exit 1; }
[[ -f "${COMBINE_SCRIPT}" ]] || { echo "ERROR: combine script not found at ${COMBINE_SCRIPT}"; exit 1; }

if [[ ${DRY_RUN} -eq 0 ]]; then
  mkdir -p "${LOCAL_BASE}"
fi

echo "==> Copying assessment_results directories from remote"
copied_count=0
missing_count=0
for i in "${!SUBPATHS[@]}"; do
  sub="${SUBPATHS[$i]}"
  remote_base_for_sub="${SUBPATH_REMOTE_BASES[$i]:-${REMOTE_BASE}}"
  sub_rel="${sub%/}"
  remote_path="${remote_base_for_sub}/${sub_rel}"
  echo "  - ${remote_path}"
  if ssh "${REMOTE}" "test -d \"${remote_path}\""; then
    if [[ ${DRY_RUN} -eq 1 ]]; then
      echo "    DRY-RUN: ssh ${REMOTE} \"tar -C '${remote_base_for_sub}' -cf - '${sub_rel}'\" | tar -C '${LOCAL_BASE}' -xf -"
    else
      ssh "${REMOTE}" "tar -C \"${remote_base_for_sub}\" -cf - \"${sub_rel}\"" | tar -C "${LOCAL_BASE}" -xf -
    fi
    copied_count=$((copied_count + 1))
  else
    echo "    WARNING: Missing remote directory, skipping: ${remote_path}"
    missing_count=$((missing_count + 1))
  fi
done

echo "==> Copy summary: found ${copied_count}, missing ${missing_count}"

if [[ ${copied_count} -eq 0 ]]; then
  echo "ERROR: None of the configured remote assessment_results directories were found."
  echo "Check --remote-base and subpaths, or update SUBPATHS in this script."
  exit 1
fi

if [[ ${DRY_RUN} -eq 1 ]]; then
  echo "\n==> Dry-run copy preview complete"
  echo "No files were copied."

  echo "==> Dry-run combine preview"
  preview_count=0
  for sub in "${SUBPATHS[@]}"; do
    sub_rel="${sub%/}"
    local_dir="${LOCAL_BASE}/${sub_rel}"

    sb_ref_tag=""
    sb_1934_tag=""
    sb_holo_tag=""
    sb_target_1934_tag=""

    if [[ "${local_dir}" =~ (SB_REF-[0-9]+) ]]; then
      sb_ref_tag="${BASH_REMATCH[1]}"
    fi
    if [[ "${local_dir}" =~ (SB_1934-[0-9]+) ]]; then
      sb_1934_tag="${BASH_REMATCH[1]}"
    fi
    if [[ "${local_dir}" =~ (SB_HOLO-[0-9]+) ]]; then
      sb_holo_tag="${BASH_REMATCH[1]}"
    fi
    if [[ "${local_dir}" =~ 1934-processing-SB-([0-9]+) ]]; then
      sb_target_1934_tag="SB_TARGET_1934-${BASH_REMATCH[1]}"
    fi

    if [[ -n "${OVERRIDE_SB_REF}" ]]; then
      sb_ref_tag="${OVERRIDE_SB_REF}"
    fi
    if [[ -n "${OVERRIDE_SB_1934}" ]]; then
      sb_1934_tag="${OVERRIDE_SB_1934}"
    fi
    if [[ -n "${OVERRIDE_SB_HOLO}" ]]; then
      sb_holo_tag="${OVERRIDE_SB_HOLO}"
    fi
    if [[ -n "${OVERRIDE_SB_TARGET_1934}" ]]; then
      sb_target_1934_tag="${OVERRIDE_SB_TARGET_1934}"
    fi

    combine_cmd=(python "${COMBINE_SCRIPT}" "${local_dir}" --dry-run)
    if [[ -n "${sb_ref_tag}" ]]; then
      combine_cmd+=(--sb-ref "${sb_ref_tag}")
    fi
    if [[ -n "${sb_1934_tag}" ]]; then
      combine_cmd+=(--sb-1934 "${sb_1934_tag}")
    fi
    if [[ -n "${sb_holo_tag}" ]]; then
      combine_cmd+=(--sb-holo "${sb_holo_tag}")
    fi
    if [[ -n "${sb_target_1934_tag}" ]]; then
      combine_cmd+=(--sb-target-1934 "${sb_target_1934_tag}")
    fi

    echo "  - ${local_dir}"
    if [[ -d "${local_dir}" ]]; then
      echo "    RUN: ${combine_cmd[*]}"
      "${combine_cmd[@]}"
      preview_count=$((preview_count + 1))
    else
      echo "    WOULD RUN: ${combine_cmd[*]}"
      echo "    NOTE: local directory not present yet (copy was dry-run)"
    fi
  done

  if [[ ${preview_count} -eq 0 ]]; then
    echo "No combine dry-run executed because no local assessment_results directories were present."
  fi

  echo "\n==> Dry-run complete"
  exit 0
fi

echo "==> Running combine_beam_outputs.py on each copied assessment_results directory"
count=0
for sub in "${SUBPATHS[@]}"; do
  sub_rel="${sub%/}"
  dir="${LOCAL_BASE}/${sub_rel}"
  if [[ ! -d "${dir}" ]]; then
    echo "WARNING: Expected local directory not found, skipping combine: ${dir}"
    continue
  fi

  count=$((count + 1))
  echo "\n[${count}] Processing: ${dir}"

  sb_ref_tag=""
  sb_1934_tag=""
  sb_holo_tag=""
  sb_target_1934_tag=""

  if [[ "${dir}" =~ (SB_REF-[0-9]+) ]]; then
    sb_ref_tag="${BASH_REMATCH[1]}"
  fi
  if [[ "${dir}" =~ (SB_1934-[0-9]+) ]]; then
    sb_1934_tag="${BASH_REMATCH[1]}"
  fi
  if [[ "${dir}" =~ (SB_HOLO-[0-9]+) ]]; then
    sb_holo_tag="${BASH_REMATCH[1]}"
  fi
  if [[ "${dir}" =~ 1934-processing-SB-([0-9]+) ]]; then
    sb_target_1934_tag="SB_TARGET_1934-${BASH_REMATCH[1]}"
  fi

  if [[ -n "${OVERRIDE_SB_REF}" ]]; then
    sb_ref_tag="${OVERRIDE_SB_REF}"
  fi
  if [[ -n "${OVERRIDE_SB_1934}" ]]; then
    sb_1934_tag="${OVERRIDE_SB_1934}"
  fi
  if [[ -n "${OVERRIDE_SB_HOLO}" ]]; then
    sb_holo_tag="${OVERRIDE_SB_HOLO}"
  fi
  if [[ -n "${OVERRIDE_SB_TARGET_1934}" ]]; then
    sb_target_1934_tag="${OVERRIDE_SB_TARGET_1934}"
  fi

  combine_cmd=(python "${COMBINE_SCRIPT}" "${dir}")
  if [[ -n "${sb_ref_tag}" ]]; then
    combine_cmd+=(--sb-ref "${sb_ref_tag}")
  fi
  if [[ -n "${sb_1934_tag}" ]]; then
    combine_cmd+=(--sb-1934 "${sb_1934_tag}")
  fi
  if [[ -n "${sb_holo_tag}" ]]; then
    combine_cmd+=(--sb-holo "${sb_holo_tag}")
  fi
  if [[ -n "${sb_target_1934_tag}" ]]; then
    combine_cmd+=(--sb-target-1934 "${sb_target_1934_tag}")
  fi

  echo "    Tags: ${sb_ref_tag:-NA} ${sb_1934_tag:-NA} ${sb_holo_tag:-NA} ${sb_target_1934_tag:-NA}"
  "${combine_cmd[@]}"
done

if [[ ${count} -eq 0 ]]; then
  echo "WARNING: No local assessment_results directories found for configured SUBPATHS under ${LOCAL_BASE}"
  exit 1
fi

echo "\n==> Complete"
echo "Copied data root: ${LOCAL_BASE}"
