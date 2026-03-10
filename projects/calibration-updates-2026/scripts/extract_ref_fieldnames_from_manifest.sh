#!/usr/bin/env bash
set -euo pipefail

SCRIPT_NAME="$(basename "$0")"
MANIFEST_FILE=""
START_INDEX=""
END_INDEX=""
OUTPUT_FILE=""

usage() {
  cat <<EOF
Usage:
  ${SCRIPT_NAME} --manifest <file> [--start-index N] [--end-index N] [--output <file>]

Description:
  Reads SB_REF values from manifest rows and queries schedblock to resolve
  REF_FIELDNAME using:
    1) common.targets
    2) common.target.<src>.field_name

Output columns:
  idx sb_ref ref_fieldname status

Notes:
  - If multiple targets are present, ref_fieldname is set to Multi.
  - If unresolved, ref_fieldname is blank and status explains why.
EOF
}

trim() {
  echo "$1" | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//'
}

normalize_key() {
  echo "$1" | tr '[:lower:]-' '[:upper:]_'
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
    --output)
      OUTPUT_FILE="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "ERROR: Unknown argument '$1'"
      usage
      exit 1
      ;;
  esac
done

[[ -n "${MANIFEST_FILE}" ]] || { echo "ERROR: --manifest is required"; exit 1; }
[[ -f "${MANIFEST_FILE}" ]] || { echo "ERROR: Manifest not found: ${MANIFEST_FILE}"; exit 1; }

if ! command -v schedblock >/dev/null 2>&1; then
  if command -v module >/dev/null 2>&1; then
    module load singularity/4.1.0-askap || true
    module use /askapbuffer/payne/raj030/askaprtModules || true
    module load askappy/2.9.1 || true
  fi
fi

command -v schedblock >/dev/null 2>&1 || { echo "ERROR: schedblock not found in PATH"; exit 1; }

parse_ref_from_token() {
  local token="$1"
  if [[ "${token}" =~ ^SB_REF-([0-9]+)$ ]]; then
    echo "${BASH_REMATCH[1]}"
  elif [[ "${token}" =~ ^[0-9]+$ ]]; then
    echo "${token}"
  else
    echo ""
  fi
}

resolve_ref_fieldname() {
  local sb_ref="$1"
  local info_output
  info_output="$(schedblock info -p "${sb_ref}" 2>/dev/null || true)"

  if [[ -z "${info_output}" ]]; then
    echo "|schedblock_unavailable"
    return
  fi

  local targets_line targets_raw
  targets_line="$(echo "${info_output}" | grep -E '^common\.targets[[:space:]]*=' | tail -n 1 || true)"
  if [[ -z "${targets_line}" ]]; then
    echo "|targets_missing"
    return
  fi

  targets_raw="$(echo "${targets_line}" | sed -E 's/^[^=]*=[[:space:]]*\[(.*)\][[:space:]]*$/\1/')"
  targets_raw="$(trim "${targets_raw}")"
  if [[ -z "${targets_raw}" ]]; then
    echo "|targets_empty"
    return
  fi

  local IFS=','
  local target_tokens=()
  read -r -a target_tokens <<< "${targets_raw}"

  local cleaned_targets=()
  local token
  for token in "${target_tokens[@]}"; do
    token="$(trim "${token}")"
    [[ -n "${token}" ]] && cleaned_targets+=("${token}")
  done

  if [[ ${#cleaned_targets[@]} -eq 0 ]]; then
    echo "|targets_empty"
    return
  fi

  if [[ ${#cleaned_targets[@]} -gt 1 ]]; then
    echo "Multi|multi_targets:${cleaned_targets[*]}"
    return
  fi

  local selected_target="${cleaned_targets[0]}"
  local field_line
  field_line="$(echo "${info_output}" | grep -E "^common\.target\.${selected_target//./\.}\.field_name[[:space:]]*=" | head -n 1 || true)"
  if [[ -z "${field_line}" ]]; then
    echo "|field_name_missing:${selected_target}"
    return
  fi

  local field_name
  field_name="$(echo "${field_line}" | sed -E 's/^[^=]*=[[:space:]]*//' | sed -E 's/[[:space:]]+$//')"
  if [[ -z "${field_name}" ]]; then
    echo "|field_name_empty:${selected_target}"
    return
  fi

  echo "${field_name}|ok"
}

emit_line() {
  local idx="$1"
  local sb_ref="$2"
  local field_name="$3"
  local status="$4"
  printf "%s\t%s\t%s\t%s\n" "${idx}" "${sb_ref}" "${field_name}" "${status}"
}

{
  echo -e "idx\tsb_ref\tref_fieldname\tstatus"

  line_no=0
  while IFS= read -r raw_line || [[ -n "${raw_line}" ]]; do
    line_no=$((line_no + 1))

    line="${raw_line%%#*}"
    line="$(trim "${line}")"
    [[ -z "${line}" ]] && continue

    if [[ "${line}" =~ ^([A-Za-z_][A-Za-z0-9_-]*)=(.+)$ ]]; then
      continue
    fi

    line="${line//,/ }"
    col1=""; col2=""; col3=""; col4=""; col5=""; col6=""; col7=""; col8=""; extra=""
    read -r col1 col2 col3 col4 col5 col6 col7 col8 extra <<< "${line}"

    idx=""
    sb_ref_token="${col1}"
    if [[ "${col1}" =~ ^[0-9]+$ ]]; then
      idx="${col1}"
      sb_ref_token="${col2}"
    fi

    col1_lc="$(echo "${sb_ref_token}" | tr '[:upper:]' '[:lower:]')"
    if [[ "${col1_lc}" == "sb_ref" || "${col1_lc}" == "sbref" ]]; then
      continue
    fi

    sb_ref="$(parse_ref_from_token "${sb_ref_token}")"
    [[ -n "${sb_ref}" ]] || continue

    if [[ -n "${START_INDEX}" && -n "${idx}" && ${idx} -lt ${START_INDEX} ]]; then
      continue
    fi
    if [[ -n "${END_INDEX}" && -n "${idx}" && ${idx} -gt ${END_INDEX} ]]; then
      continue
    fi

    result="$(resolve_ref_fieldname "${sb_ref}")"
    field_name="${result%%|*}"
    status="${result#*|}"

    emit_line "${idx:-NA}" "${sb_ref}" "${field_name}" "${status}"
  done < "${MANIFEST_FILE}"
} > "${OUTPUT_FILE:-/dev/stdout}"

if [[ -n "${OUTPUT_FILE}" ]]; then
  echo "Wrote: ${OUTPUT_FILE}"
fi
