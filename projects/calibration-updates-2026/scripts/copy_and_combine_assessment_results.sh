#!/usr/bin/env bash
set -euo pipefail

# -----------------------------
# User-configurable settings
# -----------------------------
REMOTE="raj030@setonix-dm03.pawsey.org.au"
REMOTE_BASE_ROOT="/scratch/askaprt/raj030/tickets/axa-3649-component-models/assess_1934-ref_ws-4788"
ODC_WEIGHT_ID="5231"
REMOTE_BASE="${REMOTE_BASE_ROOT}/ODC-${ODC_WEIGHT_ID}"
LOCAL_PARENT="${HOME}/DATA/reffield-average"
LOCAL_NAME="assess_1934-ref_ws-4788"
LOCAL_BASE="${LOCAL_PARENT}/${LOCAL_NAME}"
LOCAL_BASE_EXPLICIT=0
REMOTE_BASE_ROOT_EXPLICIT=0
DRY_RUN=0
COPY_METADATA=0
METADATA_ONLY=0
COMBINE_ONLY=0
OVERRIDE_SB_REF=""
OVERRIDE_SB_1934=""
OVERRIDE_SB_HOLO=""
OVERRIDE_SB_TARGET_1934=""
MANIFEST_FILE=""
START_INDEX_OVERRIDE=""
END_INDEX_OVERRIDE=""
EXCLUDE_INDICES_RAW=""
EXCLUDE_RANGE_STARTS=()
EXCLUDE_RANGE_ENDS=()

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

# Auto-detect repo root from script location.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SEARCH_DIR="${SCRIPT_DIR}"
REPO_ROOT=""
while [[ "${SEARCH_DIR}" != "/" ]]; do
  if [[ -f "${SEARCH_DIR}/setup.py" && -f "${SEARCH_DIR}/mstool/bin/combine_beam_outputs.py" ]]; then
    REPO_ROOT="${SEARCH_DIR}"
    break
  fi
  SEARCH_DIR="$(cd "${SEARCH_DIR}/.." && pwd)"
done

if [[ -z "${REPO_ROOT}" ]]; then
  echo "ERROR: Could not locate repo root containing setup.py and mstool/bin/combine_beam_outputs.py"
  exit 1
fi

COMBINE_SCRIPT="${REPO_ROOT}/mstool/bin/combine_beam_outputs.py"

# Remote subpaths to copy are constructed from SB IDs + shared naming pattern.
# Update these values for each run.
SOURCE_SB_REF_IDS=(81082 81083)
SOURCE_SB_1934_ID="77045"
SOURCE_SB_HOLO_ID="76554"
SOURCE_SB_TARGET_1934_ID="81089"
SOURCE_AMP_STRATEGY="multiply"
SOURCE_DO_PREFLAG_REFTABLE="true"

SUBPATHS=()
SUBPATH_REMOTE_BASES=()
SUBPATH_FIELD_NAMES=()

trim_whitespace() {
  echo "$1" | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//'
}

normalize_field_name_token() {
  local token
  token="$(trim_whitespace "$1")"
  if [[ -z "${token}" ]]; then
    echo ""
    return
  fi
  if [[ "${token}" =~ ^REF_FIELDNAME=(.+)$ ]]; then
    echo "$(trim_whitespace "${BASH_REMATCH[1]}")"
    return
  fi
  echo "${token}"
}

normalize_manifest_key() {
  local key
  key="$(echo "$1" | tr '[:lower:]-' '[:upper:]_')"
  echo "${key}"
}

parse_exclude_indices() {
  local raw="$1"
  EXCLUDE_RANGE_STARTS=()
  EXCLUDE_RANGE_ENDS=()

  [[ -n "${raw}" ]] || return 0

  local cleaned
  cleaned="$(echo "${raw}" | tr -d '[:space:]')"
  [[ -n "${cleaned}" ]] || return 0

  local IFS=','
  local token start end
  read -r -a tokens <<< "${cleaned}"

  for token in "${tokens[@]}"; do
    [[ -n "${token}" ]] || continue

    if [[ "${token}" =~ ^([0-9]+)-([0-9]+)$ ]]; then
      start="${BASH_REMATCH[1]}"
      end="${BASH_REMATCH[2]}"
      if [[ ${start} -gt ${end} ]]; then
        echo "ERROR: Invalid exclude range '${token}' (start > end)"
        exit 1
      fi
      EXCLUDE_RANGE_STARTS+=("${start}")
      EXCLUDE_RANGE_ENDS+=("${end}")
    elif [[ "${token}" =~ ^[0-9]+$ ]]; then
      EXCLUDE_RANGE_STARTS+=("${token}")
      EXCLUDE_RANGE_ENDS+=("${token}")
    else
      echo "ERROR: Invalid --exclude-indices token '${token}'"
      echo "       Expected comma-separated indices and/or ranges (e.g. 24-29,31,33-35)"
      exit 1
    fi
  done
}

is_row_excluded() {
  local idx="$1"
  local i start end
  for i in "${!EXCLUDE_RANGE_STARTS[@]}"; do
    start="${EXCLUDE_RANGE_STARTS[$i]}"
    end="${EXCLUDE_RANGE_ENDS[$i]}"
    if [[ ${idx} -ge ${start} && ${idx} -le ${end} ]]; then
      return 0
    fi
  done
  return 1
}

is_preflag_token() {
  local token_lc
  token_lc="$(echo "$1" | tr '[:upper:]' '[:lower:]')"
  [[ "${token_lc}" == *preflag* || "${token_lc}" == "none" || "${token_lc}" == "off" || "${token_lc}" == "on" || "${token_lc}" == "true" || "${token_lc}" == "false" ]]
}

normalize_do_preflag_value() {
  local token_lc
  token_lc="$(echo "$1" | tr '[:upper:]' '[:lower:]')"
  case "${token_lc}" in
    true|on|yes|1|insitupreflags)
      echo "true"
      ;;
    false|off|no|0|none)
      echo "false"
      ;;
    *)
      echo ""
      ;;
  esac
}

build_strategy_suffix() {
  local amp_strategy="$1"
  local do_preflag="$2"
  local suffix=""
  if [[ -n "${amp_strategy}" ]]; then
    suffix+="_AMP_STRATEGY-${amp_strategy}"
  fi
  if [[ "${do_preflag}" == "true" ]]; then
    suffix+="-insituPreflags"
  fi
  echo "${suffix}"
}

build_subpaths() {
  SUBPATHS=()
  SUBPATH_REMOTE_BASES=()
  SUBPATH_FIELD_NAMES=()
  for sb_ref_id in "${SOURCE_SB_REF_IDS[@]}"; do
    local strategy_suffix
    strategy_suffix="$(build_strategy_suffix "${SOURCE_AMP_STRATEGY}" "${SOURCE_DO_PREFLAG_REFTABLE}")"
    SUBPATHS+=(
      "SB_REF-${sb_ref_id}_SB_1934-${SOURCE_SB_1934_ID}_SB_HOLO-${SOURCE_SB_HOLO_ID}${strategy_suffix}/1934-processing-SB-${SOURCE_SB_TARGET_1934_ID}/assessment_results/"
    )
    SUBPATH_REMOTE_BASES+=("${REMOTE_BASE}")
    SUBPATH_FIELD_NAMES+=("")
  done
}

build_subpaths_from_manifest() {
  local manifest_path="$1"

  [[ -f "${manifest_path}" ]] || { echo "ERROR: --manifest file not found: ${manifest_path}"; exit 1; }

  SUBPATHS=()
  SUBPATH_REMOTE_BASES=()
  SUBPATH_FIELD_NAMES=()
  local default_field_name=""
  local auto_row_index=0
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
    # HPC_BASE_DIR=/scratch/.../assess_1934-ref_ws-4788  (canonical; also accepts REMOTE_BASE_ROOT; -qcorr appended at runtime)
    # ODC_WEIGHT_ID=5231
    # LOCAL_BASE=/Users/me/DATA/reffield-average-qcorr
    # AMP_STRATEGY=multiply
    # DO_PREFLAG_REFTABLE=true
    if [[ "${line}" =~ ^([A-Za-z_][A-Za-z0-9_]*)=(.+)$ ]]; then
      local cfg_key="${BASH_REMATCH[1]}"
      local cfg_val="${BASH_REMATCH[2]}"
      cfg_val="$(trim_whitespace "${cfg_val}")"

      case "${cfg_key}" in
        REMOTE)
          REMOTE="${cfg_val}"
          ;;
        REMOTE_BASE)
          REMOTE_BASE="${cfg_val}"
          ;;
        HPC_BASE_DIR)
          [[ ${REMOTE_BASE_ROOT_EXPLICIT} -eq 0 ]] && REMOTE_BASE_ROOT="${cfg_val}"
          ;;
        REMOTE_BASE_ROOT)
          [[ ${REMOTE_BASE_ROOT_EXPLICIT} -eq 0 ]] && REMOTE_BASE_ROOT="${cfg_val}"
          ;;
        ODC_WEIGHT_ID|ODC|WEIGHT_ID)
          ODC_WEIGHT_ID="${cfg_val}"
          ;;
        LOCAL_BASE)
          if [[ ${LOCAL_BASE_EXPLICIT} -eq 0 ]]; then
            LOCAL_BASE="${cfg_val}"
            LOCAL_BASE_EXPLICIT=1
          fi
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
        DO_PREFLAG_REFTABLE|PREFLAGGING_STRATEGY|PREFLAG_STRATEGY|FLAG_STRATEGY)
          local normalized_preflag
          normalized_preflag="$(normalize_do_preflag_value "${cfg_val}")"
          if [[ -z "${normalized_preflag}" ]]; then
            echo "WARNING: Invalid DO_PREFLAG_REFTABLE value '${cfg_val}' on line ${line_no}; expected true/false or insituPreflags/none"
          else
            SOURCE_DO_PREFLAG_REFTABLE="${normalized_preflag}"
          fi
          ;;
        REF_FIELDNAME)
          default_field_name="$(normalize_field_name_token "${cfg_val}")"
          ;;
        *)
          echo "WARNING: Unknown manifest config key '${cfg_key}' on line ${line_no}; ignoring"
          ;;
      esac
      continue
    fi

    # Accept comma- or whitespace-separated fields for SBID rows
    line="${line//,/ }"
    local col1="" col2="" col3="" col4="" col5="" col6="" col7="" col8="" extra=""
    local row_index=""
    read -r col1 col2 col3 col4 col5 col6 col7 col8 extra <<< "${line}"

    # Optional leading row index:
    # idx sb_ref sb_1934 sb_holo sb_target_1934 [odc_weight_id] [amp_strategy] [do_preflag_reftable] [REF_FIELDNAME=<name>]
    if [[ "${col1}" =~ ^[0-9]+$ ]]; then
      row_index="${col1}"
      col1="${col2}"
      col2="${col3}"
      col3="${col4}"
      col4="${col5}"
      col5="${col6}"
      col6="${col7}"
      col7="${col8}"
      col8="${extra}"
      extra=""
    else
      row_index="${auto_row_index}"
    fi
    auto_row_index=$((auto_row_index + 1))

    # Skip header line if present
    local col1_lc
    col1_lc="$(echo "${col1}" | tr '[:upper:]' '[:lower:]')"
    if [[ "${col1_lc}" == "sb_ref" || "${col1_lc}" == "sbref" ]]; then
      continue
    fi

    if [[ -z "${col1}" || -z "${col2}" || -z "${col3}" || -z "${col4}" ]]; then
      echo "WARNING: Skipping manifest line ${line_no}: expected 4 to 9 columns ([idx] sb_ref sb_1934 sb_holo sb_target_1934 [odc_weight_id] [amp_strategy] [do_preflag_reftable] [REF_FIELDNAME=<name>])"
      continue
    fi

    if [[ -n "${START_INDEX_OVERRIDE}" && ${row_index} -lt ${START_INDEX_OVERRIDE} ]]; then
      continue
    fi
    if [[ -n "${END_INDEX_OVERRIDE}" && ${row_index} -gt ${END_INDEX_OVERRIDE} ]]; then
      continue
    fi
    if is_row_excluded "${row_index}"; then
      continue
    fi

    local sb_ref_tag sb_1934_tag sb_holo_tag sb_target_tag amp_strategy row_do_preflag row_odc_weight row_remote_base row_field_name row_amp_set row_field_set
    sb_ref_tag="$(normalize_tag "${col1}" "SB_REF-")"
    sb_1934_tag="$(normalize_tag "${col2}" "SB_1934-")"
    sb_holo_tag="$(normalize_tag "${col3}" "SB_HOLO-")"
    sb_target_tag="$(normalize_tag "${col4}" "SB_TARGET_1934-")"
    amp_strategy="${SOURCE_AMP_STRATEGY}"
    row_do_preflag="${SOURCE_DO_PREFLAG_REFTABLE}"
    row_odc_weight=""
    row_field_name="${default_field_name}"
    row_amp_set=0
    row_field_set=0

    local token
    for token in "${col5}" "${col6}" "${col7}" "${col8}"; do
      [[ -z "${token}" ]] && continue
      if [[ "${token}" =~ ^([A-Za-z_][A-Za-z0-9_-]*)=(.+)$ ]]; then
        local token_key token_val normalized_key normalized_row_preflag
        token_key="${BASH_REMATCH[1]}"
        token_val="${BASH_REMATCH[2]}"
        token_val="$(trim_whitespace "${token_val}")"
        normalized_key="$(normalize_manifest_key "${token_key}")"
        case "${normalized_key}" in
          ODC_WEIGHT|ODC_WEIGHT_ID|ODC|WEIGHT_ID)
            row_odc_weight="${token_val}"
            ;;
          AMP_STRATEGY)
            amp_strategy="${token_val}"
            row_amp_set=1
            ;;
          DO_PREFLAG_REFTABLE|DO_PREFLAG|PREFLAGGING_STRATEGY|PREFLAG_STRATEGY|FLAG_STRATEGY)
            normalized_row_preflag="$(normalize_do_preflag_value "${token_val}")"
            if [[ -z "${normalized_row_preflag}" ]]; then
              echo "WARNING: Skipping manifest line ${line_no}: invalid do_preflag token '${token_val}'"
              continue 2
            fi
            row_do_preflag="${normalized_row_preflag}"
            ;;
          REF_FIELDNAME)
            if [[ ${row_field_set} -eq 1 ]]; then
              echo "WARNING: Skipping manifest line ${line_no}: multiple REF_FIELDNAME values provided"
              continue 2
            fi
            row_field_name="$(normalize_field_name_token "REF_FIELDNAME=${token_val}")"
            row_field_set=1
            ;;
          *)
            echo "WARNING: Skipping manifest line ${line_no}: unknown key '${token_key}'"
            continue 2
            ;;
        esac
      else
        echo "WARNING: Skipping manifest line ${line_no}: unkeyed optional token '${token}' (use KEY=VALUE format)"
        continue 2
      fi
    done

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
      "SB_REF-${sb_ref_id}_SB_1934-${sb_1934_id}_SB_HOLO-${sb_holo_id}$(build_strategy_suffix "${amp_strategy}" "${row_do_preflag}")/1934-processing-SB-${sb_target_id}/assessment_results/"
    )
    row_remote_base="$(resolve_remote_base_for_odc "${row_odc_weight}")" || exit 1
    SUBPATH_REMOTE_BASES+=("${row_remote_base}")
    SUBPATH_FIELD_NAMES+=("${row_field_name}")
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
  --copy-metadata           Also copy tuple sibling metadata/ directories (default: off).
  --metadata-only           Fetch only tuple sibling metadata/ directories; skip assessment copy and combine.
  --combine-only            Skip all remote SSH/copy steps; run combine_beam_outputs.py on already-local data only.
  --remote USER@HOST        Remote SSH target (default: raj030@setonix-dm03.pawsey.org.au).
  --odc-weight-id ID        ODC weight ID (e.g. 5231 or ODC-5231).
  --remote-base PATH        Remote base directory containing SB_REF-* paths.
  --remote-base-root PATH   Remote base root; REMOTE_BASE becomes <root>/ODC-<ID> when ODC is set.
  --local-base PATH         Full local destination path (overrides parent/name options).
  --local-parent PATH       Parent directory for local copy destination.
  --local-name NAME         Directory name under --local-parent.
  --manifest FILE           ASCII file listing SBID combinations and optional config directives.
  --start-index N           Start manifest row index (inclusive, requires --manifest).
  --end-index N             End manifest row index (inclusive, requires --manifest).
  --exclude-indices SPEC    Comma-separated manifest indices/ranges to skip (requires --manifest),
                            e.g. 24-29 or 24-29,31,33-35.
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
          DO_PREFLAG_REFTABLE=...   (aliases: PREFLAGGING_STRATEGY, PREFLAG_STRATEGY, FLAG_STRATEGY)
  - SB rows (space or comma separated):
      [idx] sb_ref sb_1934 sb_holo sb_target_1934 [optional tokens]
      (optional tokens are order-independent but must be key=value;
       e.g. ODC_WEIGHT=5231 AMP_STRATEGY=multiply DO_PREFLAG_REFTABLE=true REF_FIELDNAME=REF_0324-28)
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run)
      DRY_RUN=1
      shift
      ;;
    --copy-metadata)
      COPY_METADATA=1
      shift
      ;;
    --metadata-only)
      METADATA_ONLY=1
      COPY_METADATA=1
      shift
      ;;
    --combine-only)
      COMBINE_ONLY=1
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
      REMOTE_BASE_ROOT_EXPLICIT=1
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
    --start-index)
      [[ $# -ge 2 ]] || { echo "ERROR: --start-index requires a value"; exit 1; }
      START_INDEX_OVERRIDE="$2"
      shift 2
      ;;
    --end-index)
      [[ $# -ge 2 ]] || { echo "ERROR: --end-index requires a value"; exit 1; }
      END_INDEX_OVERRIDE="$2"
      shift 2
      ;;
    --exclude-indices)
      [[ $# -ge 2 ]] || { echo "ERROR: --exclude-indices requires a value"; exit 1; }
      EXCLUDE_INDICES_RAW="$2"
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

if [[ -n "${START_INDEX_OVERRIDE}" && ! "${START_INDEX_OVERRIDE}" =~ ^[0-9]+$ ]]; then
  echo "ERROR: --start-index must be a non-negative integer"
  exit 1
fi
if [[ -n "${END_INDEX_OVERRIDE}" && ! "${END_INDEX_OVERRIDE}" =~ ^[0-9]+$ ]]; then
  echo "ERROR: --end-index must be a non-negative integer"
  exit 1
fi
if [[ -n "${START_INDEX_OVERRIDE}" && -n "${END_INDEX_OVERRIDE}" && ${START_INDEX_OVERRIDE} -gt ${END_INDEX_OVERRIDE} ]]; then
  echo "ERROR: --start-index cannot be greater than --end-index"
  exit 1
fi
if [[ -z "${MANIFEST_FILE}" && ( -n "${START_INDEX_OVERRIDE}" || -n "${END_INDEX_OVERRIDE}" ) ]]; then
  echo "ERROR: --start-index/--end-index requires --manifest"
  exit 1
fi
if [[ -z "${MANIFEST_FILE}" && -n "${EXCLUDE_INDICES_RAW}" ]]; then
  echo "ERROR: --exclude-indices requires --manifest"
  exit 1
fi

parse_exclude_indices "${EXCLUDE_INDICES_RAW}"

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
echo "  Remote host    : ${REMOTE}"
echo "  Remote base root: ${REMOTE_BASE_ROOT:-${REMOTE_BASE}}"
echo "  ODC weight ID (global default, per-row may differ): ${ODC_WEIGHT_ID:-none}"
echo "  Local destination: ${LOCAL_BASE}"
echo "  Dry run: ${DRY_RUN}"
echo "  Copy metadata: ${COPY_METADATA}"
echo "  Metadata only: ${METADATA_ONLY}"
echo "  Combine only:  ${COMBINE_ONLY}"
echo "  Manifest: ${MANIFEST_FILE:-none}"
echo "  Manifest row range: ${START_INDEX_OVERRIDE:-all}..${END_INDEX_OVERRIDE:-all}"
echo "  Excluded indices: ${EXCLUDE_INDICES_RAW:-none}"
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
if [[ ${COMBINE_ONLY} -eq 0 ]]; then
  command -v ssh >/dev/null 2>&1 || { echo "ERROR: ssh not found"; exit 1; }
fi
[[ -f "${COMBINE_SCRIPT}" ]] || { echo "ERROR: combine script not found at ${COMBINE_SCRIPT}"; exit 1; }

if [[ ${DRY_RUN} -eq 0 ]]; then
  mkdir -p "${LOCAL_BASE}"
fi

# Open a persistent SSH ControlMaster connection so all subsequent ssh calls
# reuse a single TCP channel, avoiding connection-rate limits on the remote.
SSH_MUX_PATH="/tmp/ssh_mux_copy_$$"
if [[ ${COMBINE_ONLY} -eq 0 ]]; then
  ssh -MNf \
    -o ControlPath="${SSH_MUX_PATH}" \
    -o ControlPersist=300 \
    "${REMOTE}"
  trap 'ssh -S "${SSH_MUX_PATH}" -O exit "${REMOTE}" 2>/dev/null; rm -f "${SSH_MUX_PATH}"' EXIT
fi

# Thin wrapper: run ssh via the multiplexed channel.
ssh_mux() { ssh -o ControlPath="${SSH_MUX_PATH}" "$@"; }

echo "==> Copying assessment_results directories from remote"
copied_count=0
missing_count=0
metadata_copied_count=0
metadata_skipped_existing_count=0
metadata_missing_count=0
for i in "${!SUBPATHS[@]}"; do
  sub="${SUBPATHS[$i]}"
  remote_base_for_sub="${SUBPATH_REMOTE_BASES[$i]:-${REMOTE_BASE}}"
  sub_rel="${sub%/}"
  remote_path="${remote_base_for_sub}/${sub_rel}"
  echo "  [$(( i + 1 ))/${#SUBPATHS[@]}] Source: ${REMOTE}:${remote_path}"
  if [[ ${METADATA_ONLY} -eq 0 && ${COMBINE_ONLY} -eq 0 ]]; then
    if [[ ${DRY_RUN} -eq 1 ]]; then
      if ssh_mux "${REMOTE}" "test -d \"${remote_path}\""; then
        echo "    DRY-RUN: ssh ${REMOTE} \"tar -C '${remote_base_for_sub}' -cf - '${sub_rel}'\" | tar -C '${LOCAL_BASE}' -xf -"
        copied_count=$((copied_count + 1))
      else
        echo "    WARNING: Missing remote directory, skipping: ${remote_path}"
        missing_count=$((missing_count + 1))
      fi
    else
      # Single SSH call: exits 2 if dir missing, 0 on success (options 2+3).
      set +o pipefail
      ssh_mux "${REMOTE}" "test -d \"${remote_path}\" || exit 2; tar -C \"${remote_base_for_sub}\" -cf - \"${sub_rel}\"" \
        | tar -C "${LOCAL_BASE}" -xf -
      _pipe=("${PIPESTATUS[@]}")
      set -o pipefail
      if [[ ${_pipe[0]} -eq 2 ]]; then
        echo "    WARNING: Missing remote directory, skipping: ${remote_path}"
        missing_count=$((missing_count + 1))
      elif [[ ${_pipe[0]} -ne 0 || ${_pipe[1]} -ne 0 ]]; then
        echo "    ERROR: Transfer failed (ssh_rc=${_pipe[0]} tar_rc=${_pipe[1]}): ${remote_path}"
        exit 1
      else
        copied_count=$((copied_count + 1))
      fi
    fi
  fi

  if [[ ${COPY_METADATA} -eq 1 ]]; then
    tuple_rel="$(echo "${sub_rel}" | sed -E 's#/1934-processing-SB-[0-9]+/assessment_results$##')"
    if [[ -z "${tuple_rel}" || "${tuple_rel}" == "${sub_rel}" ]]; then
      echo "    WARNING: Could not derive tuple root from subpath, skipping metadata copy for: ${sub_rel}"
      metadata_missing_count=$((metadata_missing_count + 1))
      continue
    fi

    local_metadata_dir="${LOCAL_BASE}/${tuple_rel}/metadata"
    remote_metadata_path="${remote_base_for_sub}/${tuple_rel}/metadata"

    if [[ -d "${local_metadata_dir}" ]]; then
      echo "    METADATA: local metadata already exists, skipping fetch: ${local_metadata_dir}"
      metadata_skipped_existing_count=$((metadata_skipped_existing_count + 1))
      continue
    fi

    if [[ ${DRY_RUN} -eq 1 ]]; then
      if ssh_mux "${REMOTE}" "test -d \"${remote_metadata_path}\""; then
        echo "    DRY-RUN METADATA: ssh ${REMOTE} \"tar -C '${remote_base_for_sub}' -cf - '${tuple_rel}/metadata'\" | tar -C '${LOCAL_BASE}' -xf -"
        metadata_copied_count=$((metadata_copied_count + 1))
      else
        echo "    WARNING: Missing remote metadata directory, skipping: ${remote_metadata_path}"
        metadata_missing_count=$((metadata_missing_count + 1))
      fi
    else
      # Single SSH call: exits 2 if dir missing, 0 on success (options 2+3).
      set +o pipefail
      ssh_mux "${REMOTE}" "test -d \"${remote_metadata_path}\" || exit 2; tar -C \"${remote_base_for_sub}\" -cf - \"${tuple_rel}/metadata\"" \
        | tar -C "${LOCAL_BASE}" -xf -
      _pipe=("${PIPESTATUS[@]}")
      set -o pipefail
      if [[ ${_pipe[0]} -eq 2 ]]; then
        echo "    WARNING: Missing remote metadata directory, skipping: ${remote_metadata_path}"
        metadata_missing_count=$((metadata_missing_count + 1))
      elif [[ ${_pipe[0]} -ne 0 || ${_pipe[1]} -ne 0 ]]; then
        echo "    ERROR: Metadata transfer failed (ssh_rc=${_pipe[0]} tar_rc=${_pipe[1]}): ${remote_metadata_path}"
        exit 1
      else
        metadata_copied_count=$((metadata_copied_count + 1))
      fi
    fi
  fi
done

if [[ ${METADATA_ONLY} -eq 1 ]]; then
  echo "==> Assessment copy summary: skipped (metadata-only mode)"
elif [[ ${COMBINE_ONLY} -eq 1 ]]; then
  echo "==> Assessment copy summary: skipped (combine-only mode)"
else
  echo "==> Copy summary: found ${copied_count}, missing ${missing_count}"
fi
if [[ ${COPY_METADATA} -eq 1 ]]; then
  echo "==> Metadata copy summary: copied ${metadata_copied_count}, skipped-existing ${metadata_skipped_existing_count}, missing ${metadata_missing_count}"
fi

if [[ ${METADATA_ONLY} -eq 0 && ${COMBINE_ONLY} -eq 0 && ${copied_count} -eq 0 ]]; then
  echo "ERROR: None of the configured remote assessment_results directories were found."
  echo "Check --remote-base and subpaths, or update SUBPATHS in this script."
  exit 1
fi

if [[ ${METADATA_ONLY} -eq 1 ]]; then
  if [[ $((metadata_copied_count + metadata_skipped_existing_count)) -eq 0 ]]; then
    echo "WARNING: No metadata directories were copied or already available locally."
  fi
  if [[ ${DRY_RUN} -eq 1 ]]; then
    echo "\n==> Dry-run metadata-only preview complete"
    echo "No files were copied."
  else
    echo "\n==> Metadata-only fetch complete"
  fi
  exit 0
fi

if [[ ${DRY_RUN} -eq 1 ]]; then
  echo "\n==> Dry-run copy preview complete"
  echo "No files were copied."

  echo "==> Dry-run combine preview"
  preview_count=0
  for i in "${!SUBPATHS[@]}"; do
    sub="${SUBPATHS[$i]}"
    field_name_now="$(trim_whitespace "${SUBPATH_FIELD_NAMES[$i]:-}")"
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
    if [[ -n "${field_name_now}" ]]; then
      combine_cmd+=(--field-name "${field_name_now}")
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
for i in "${!SUBPATHS[@]}"; do
  sub="${SUBPATHS[$i]}"
  field_name_now="$(trim_whitespace "${SUBPATH_FIELD_NAMES[$i]:-}")"
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
  if [[ -n "${field_name_now}" ]]; then
    combine_cmd+=(--field-name "${field_name_now}")
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
