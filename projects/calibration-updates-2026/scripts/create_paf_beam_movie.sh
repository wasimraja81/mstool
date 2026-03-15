#!/usr/bin/env bash
# create_paf_beam_movie.sh
#
# Generate PAF beam-overlay movies (MP4) for one or more SB_REFs driven by a
# manifest file.  Uses the same manifest / index-filtering conventions as
# copy_and_combine_assessment_results.sh.
#
# Run from the repo root (or use the convenience wrapper run_paf_beam_movie.sh):
#   bash projects/calibration-updates-2026/scripts/create_paf_beam_movie.sh \
#       --manifest projects/calibration-updates-2026/manifests/sb_manifest_reffield_average.txt \
#       --start-index 14 --end-index 42 --exclude-indices 24-29
#
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

# ── Defaults ─────────────────────────────────────────────────────────────────
MANIFEST_FILE=""
START_INDEX_OVERRIDE=""
END_INDEX_OVERRIDE=""
EXCLUDE_INDICES_RAW=""
EXCLUDE_RANGE_STARTS=()
EXCLUDE_RANGE_ENDS=()

DATA_ROOT="${HOME}/DATA/reffield-average"
OUTPUT_DIR=""          # defaults to ${DATA_ROOT}/phase3/plots

# Global manifest defaults (can be overridden per-row or by manifest-level KEY=VALUE)
DEFAULT_AMP_STRATEGY="multiply"
DEFAULT_DO_PREFLAG="true"

# Movie parameters (all overridable via CLI)
FPS=3
N_NULLS=3
TRAIL=0.22
GAMMA=0.45
CMAP="gray"
DPI=150
HOLD=2
GRID_RES=500
FORCE=0    # set --force to regenerate existing files

# ── Repo / script location ────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_SCRIPT="${SCRIPT_DIR}/plot_paf_beam_movie.py"

SEARCH_DIR="${SCRIPT_DIR}"
REPO_ROOT=""
while [[ "${SEARCH_DIR}" != "/" ]]; do
  if [[ -f "${SEARCH_DIR}/setup.py" ]]; then
    REPO_ROOT="${SEARCH_DIR}"; break
  fi
  SEARCH_DIR="$(cd "${SEARCH_DIR}/.." && pwd)"
done
[[ -n "${REPO_ROOT}" ]] || { echo "ERROR: Could not locate repo root (setup.py)"; exit 1; }

VENV="${REPO_ROOT}/.venv"
[[ -f "${VENV}/bin/activate" ]] && source "${VENV}/bin/activate"

# ── Helper functions ──────────────────────────────────────────────────────────
trim_whitespace() { echo "$1" | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//'; }
normalize_manifest_key() { echo "$1" | tr '[:lower:]-' '[:upper:]_'; }
normalize_do_preflag_value() {
  local v; v="$(echo "$1" | tr '[:upper:]' '[:lower:]')"
  case "${v}" in
    true|on|yes|1|insitupreflags) echo "true"  ;;
    false|off|no|0|none)          echo "false" ;;
    *)                             echo ""      ;;
  esac
}
# Build the strategy suffix:  _AMP_STRATEGY-<amp>[-insituPreflags]
build_strategy_suffix() {
  local amp="$1" preflag="$2" suffix=""
  [[ -n "${amp}" ]]           && suffix+="_AMP_STRATEGY-${amp}"
  [[ "${preflag}" == "true" ]] && suffix+="-insituPreflags"
  echo "${suffix}"
}

parse_exclude_indices() {
  local raw="$1"
  EXCLUDE_RANGE_STARTS=(); EXCLUDE_RANGE_ENDS=()
  [[ -n "${raw}" ]] || return 0
  local cleaned; cleaned="$(echo "${raw}" | tr -d '[:space:]')"
  [[ -n "${cleaned}" ]] || return 0
  local IFS=',' token start end
  read -r -a tokens <<< "${cleaned}"
  for token in "${tokens[@]}"; do
    [[ -n "${token}" ]] || continue
    if [[ "${token}" =~ ^([0-9]+)-([0-9]+)$ ]]; then
      start="${BASH_REMATCH[1]}"; end="${BASH_REMATCH[2]}"
      [[ ${start} -le ${end} ]] || { echo "ERROR: Invalid exclude range '${token}'"; exit 1; }
      EXCLUDE_RANGE_STARTS+=("${start}"); EXCLUDE_RANGE_ENDS+=("${end}")
    elif [[ "${token}" =~ ^[0-9]+$ ]]; then
      EXCLUDE_RANGE_STARTS+=("${token}"); EXCLUDE_RANGE_ENDS+=("${token}")
    else
      echo "ERROR: Invalid --exclude-indices token '${token}'"; exit 1
    fi
  done
}

is_row_excluded() {
  local idx="$1" i start end
  for i in "${!EXCLUDE_RANGE_STARTS[@]}"; do
    start="${EXCLUDE_RANGE_STARTS[$i]}"; end="${EXCLUDE_RANGE_ENDS[$i]}"
    [[ ${idx} -ge ${start} && ${idx} -le ${end} ]] && return 0
  done
  return 1
}

# ── Usage ─────────────────────────────────────────────────────────────────────
usage() {
  cat << 'EOF'
Usage:
  create_paf_beam_movie.sh [options]

Manifest / index options:
  --manifest FILE           Manifest file (sb_manifest_reffield_average.txt)
  --start-index N           First manifest index to process (inclusive)
  --end-index N             Last manifest index to process (inclusive)
  --exclude-indices SPEC    Indices/ranges to skip, e.g. 24-29 or 24-29,31

Data options:
  --data-root PATH          Local data root (default: ~/DATA/reffield-average)
  --output-dir PATH         Output directory for MP4s (default: <data-root>/phase3/plots)
  (AMP_STRATEGY and DO_PREFLAG_REFTABLE are read per-row from the manifest;
   global manifest defaults: AMP_STRATEGY=multiply, DO_PREFLAG_REFTABLE=true)

Movie options:
  --fps N                   Frames per second (default: 3)
  --n-nulls N               Airy nulls to show: 1, 2, or 3 (default: 3)
  --trail F                 Ghost-trail alpha scale 0-1 (default: 0.22)
  --gamma F                 Display gamma for ring contrast (default: 0.45)
  --cmap NAME               Matplotlib colourmap: gray | Blues | hot | plasma
                            (default: gray)
  --dpi N                   Output resolution DPI (default: 150)
  --hold N                  Hold frames at end of movie (default: 2)
  --grid-res N              Airy grid resolution in pixels (default: 500)
  --force                   Regenerate even if output MP4 already exists

  -h, --help                Show this help.

Examples:
  # All active SB_REFs, excluding ODC-5233:
  create_paf_beam_movie.sh \
    --manifest projects/calibration-updates-2026/manifests/sb_manifest_reffield_average.txt \
    --start-index 14 --end-index 42 --exclude-indices 24-29

  # Single index:
  create_paf_beam_movie.sh \
    --manifest projects/calibration-updates-2026/manifests/sb_manifest_reffield_average.txt \
    --start-index 19 --end-index 19

  # Blues colourmap, slower playback:
  create_paf_beam_movie.sh --manifest ... --cmap Blues --fps 2
EOF
}

# ── Argument parsing ──────────────────────────────────────────────────────────
while [[ $# -gt 0 ]]; do
  case "$1" in
    --manifest)
      [[ $# -ge 2 ]] || { echo "ERROR: --manifest requires a value"; exit 1; }
      MANIFEST_FILE="$2"; shift 2 ;;
    --start-index)
      [[ $# -ge 2 ]] || { echo "ERROR: --start-index requires a value"; exit 1; }
      START_INDEX_OVERRIDE="$2"; shift 2 ;;
    --end-index)
      [[ $# -ge 2 ]] || { echo "ERROR: --end-index requires a value"; exit 1; }
      END_INDEX_OVERRIDE="$2"; shift 2 ;;
    --exclude-indices)
      [[ $# -ge 2 ]] || { echo "ERROR: --exclude-indices requires a value"; exit 1; }
      EXCLUDE_INDICES_RAW="$2"; shift 2 ;;
    --data-root)
      [[ $# -ge 2 ]] || { echo "ERROR: --data-root requires a value"; exit 1; }
      DATA_ROOT="$2"; shift 2 ;;
    --output-dir)
      [[ $# -ge 2 ]] || { echo "ERROR: --output-dir requires a value"; exit 1; }
      OUTPUT_DIR="$2"; shift 2 ;;
    --fps)
      [[ $# -ge 2 ]] || { echo "ERROR: --fps requires a value"; exit 1; }
      FPS="$2"; shift 2 ;;
    --n-nulls)
      [[ $# -ge 2 ]] || { echo "ERROR: --n-nulls requires a value"; exit 1; }
      N_NULLS="$2"; shift 2 ;;
    --trail)
      [[ $# -ge 2 ]] || { echo "ERROR: --trail requires a value"; exit 1; }
      TRAIL="$2"; shift 2 ;;
    --gamma)
      [[ $# -ge 2 ]] || { echo "ERROR: --gamma requires a value"; exit 1; }
      GAMMA="$2"; shift 2 ;;
    --cmap)
      [[ $# -ge 2 ]] || { echo "ERROR: --cmap requires a value"; exit 1; }
      CMAP="$2"; shift 2 ;;
    --dpi)
      [[ $# -ge 2 ]] || { echo "ERROR: --dpi requires a value"; exit 1; }
      DPI="$2"; shift 2 ;;
    --hold)
      [[ $# -ge 2 ]] || { echo "ERROR: --hold requires a value"; exit 1; }
      HOLD="$2"; shift 2 ;;
    --grid-res)
      [[ $# -ge 2 ]] || { echo "ERROR: --grid-res requires a value"; exit 1; }
      GRID_RES="$2"; shift 2 ;;
    --force)
      FORCE=1; shift ;;
    -h|--help)
      usage; exit 0 ;;
    *)
      echo "ERROR: Unknown option '$1'"; usage; exit 1 ;;
  esac
done

# ── Resolve paths ─────────────────────────────────────────────────────────────
[[ -z "${OUTPUT_DIR}" ]] && OUTPUT_DIR="${DATA_ROOT}/phase3/plots"

if [[ -z "${MANIFEST_FILE}" ]]; then
  CANDIDATE="${SCRIPT_DIR}/../manifests/sb_manifest_reffield_average.txt"
  [[ -f "${CANDIDATE}" ]] && MANIFEST_FILE="${CANDIDATE}"
fi
[[ -n "${MANIFEST_FILE}" && -f "${MANIFEST_FILE}" ]] || {
  echo "ERROR: No manifest file found. Provide --manifest <path>."
  exit 1
}

parse_exclude_indices "${EXCLUDE_INDICES_RAW}"
mkdir -p "${OUTPUT_DIR}"

echo "=== create_paf_beam_movie.sh ==="
echo "  Manifest     : ${MANIFEST_FILE}"
echo "  Index range  : ${START_INDEX_OVERRIDE:-all}..${END_INDEX_OVERRIDE:-all}"
echo "  Excluded     : ${EXCLUDE_INDICES_RAW:-none}"
echo "  Data root    : ${DATA_ROOT}"
echo "  Output dir   : ${OUTPUT_DIR}"
echo "  fps=${FPS}  n_nulls=${N_NULLS}  trail=${TRAIL}  gamma=${GAMMA}  cmap=${CMAP}  dpi=${DPI}"
echo ""

# ── Parse manifest and process rows ──────────────────────────────────────────
ok_count=0; skip_count=0; fail_count=0; missing_meta_count=0
line_no=0

while IFS= read -r raw_line || [[ -n "${raw_line}" ]]; do
  line_no=$((line_no + 1))
  line="${raw_line%%#*}"
  line="$(trim_whitespace "${line}")"
  [[ -z "${line}" ]] && continue
  # Global manifest config directive (KEY=VALUE line)
  if [[ "${line}" =~ ^([A-Za-z_][A-Za-z0-9_-]*)=(.+)$ ]]; then
    cfg_key="$(normalize_manifest_key "${BASH_REMATCH[1]}")"
    cfg_val="$(trim_whitespace "${BASH_REMATCH[2]}")"
    case "${cfg_key}" in
      AMP_STRATEGY)
        DEFAULT_AMP_STRATEGY="${cfg_val}" ;;
      DO_PREFLAG_REFTABLE|DO_PREFLAG|PREFLAGGING_STRATEGY|PREFLAG_STRATEGY|FLAG_STRATEGY)
        n="$(normalize_do_preflag_value "${cfg_val}")"
        [[ -n "${n}" ]] && DEFAULT_DO_PREFLAG="${n}" ;;
      LOCAL_BASE|DATA_ROOT)
        DATA_ROOT="${cfg_val}" ;;
    esac
    continue
  fi

  read -r -a toks <<< "${line}"
  [[ ${#toks[@]} -lt 5 ]] && continue
  [[ "${toks[0]}" =~ ^[0-9]+$ ]] || continue

  idx="${toks[0]}"
  sb_ref="${toks[1]#SB_REF-}"
  sb_1934="${toks[2]#SB_1934-}"
  sb_holo="${toks[3]#SB_HOLO-}"

  ref_fieldname=""
  row_amp="${DEFAULT_AMP_STRATEGY}"
  row_preflag="${DEFAULT_DO_PREFLAG}"
  for tok in "${toks[@]:5}"; do
    [[ -z "${tok}" ]] && continue
    if [[ "${tok}" =~ ^([A-Za-z_][A-Za-z0-9_-]*)=(.+)$ ]]; then
      tk="$(normalize_manifest_key "${BASH_REMATCH[1]}")"
      tv="$(trim_whitespace "${BASH_REMATCH[2]}")"
      case "${tk}" in
        REF_FIELDNAME)
          ref_fieldname="${tv}" ;;
        AMP_STRATEGY)
          row_amp="${tv}" ;;
        DO_PREFLAG_REFTABLE|DO_PREFLAG|PREFLAGGING_STRATEGY|PREFLAG_STRATEGY|FLAG_STRATEGY)
          n="$(normalize_do_preflag_value "${tv}")"
          [[ -n "${n}" ]] && row_preflag="${n}" ;;
        ODC_WEIGHT|ODC_WEIGHT_ID|ODC) ;;
        *) ;;
      esac
    fi
  done

  # Index filtering
  [[ -n "${START_INDEX_OVERRIDE}" && ${idx} -lt ${START_INDEX_OVERRIDE} ]] && continue
  [[ -n "${END_INDEX_OVERRIDE}"   && ${idx} -gt ${END_INDEX_OVERRIDE}   ]] && continue
  if is_row_excluded "${idx}"; then
    echo "  [idx=${idx} SB_REF=${sb_ref}] skipped (excluded)"; skip_count=$((skip_count+1)); continue
  fi
  if [[ -z "${ref_fieldname}" ]]; then
    echo "  [idx=${idx} SB_REF=${sb_ref}] skipped (no REF_FIELDNAME)"; skip_count=$((skip_count+1)); continue
  fi

  # Locate metadata
  strategy_suffix="$(build_strategy_suffix "${row_amp}" "${row_preflag}")"
  meta_dir="${DATA_ROOT}/SB_REF-${sb_ref}_SB_1934-${sb_1934}_SB_HOLO-${sb_holo}${strategy_suffix}/metadata"
  footprint="${meta_dir}/footprintOutput-sb${sb_ref}-${ref_fieldname}.txt"
  [[ -f "${footprint}" ]] || footprint="${meta_dir}/footprintOutput-sb${sb_ref}-src1-${ref_fieldname}.txt"
  schedblock="${meta_dir}/schedblock-info-${sb_ref}.txt"
  [[ -f "${schedblock}" ]] || schedblock="${meta_dir}/schedblock-info-${sb_1934}.txt"

  if [[ ! -f "${footprint}" || ! -f "${schedblock}" ]]; then
    echo "  [idx=${idx} SB_REF=${sb_ref}] SKIP — metadata not found in ${meta_dir}"
    missing_meta_count=$((missing_meta_count+1)); continue
  fi

  output_mp4="${OUTPUT_DIR}/paf_beam_movie_${sb_ref}.mp4"
  if [[ -f "${output_mp4}" && ${FORCE} -eq 0 ]]; then
    echo "  [idx=${idx} SB_REF=${sb_ref}] already exists, skipping (--force to regenerate)"
    skip_count=$((skip_count+1)); continue
  fi

  echo "  [idx=${idx} SB_REF=${sb_ref} ${ref_fieldname}] amp=${row_amp} preflag=${row_preflag} generating …"
  if python "${PYTHON_SCRIPT}" \
       --footprint  "${footprint}"  \
       --schedblock "${schedblock}" \
       --output     "${output_mp4}" \
       --fps        "${FPS}"        \
       --n-nulls    "${N_NULLS}"    \
       --trail      "${TRAIL}"      \
       --gamma      "${GAMMA}"      \
       --cmap       "${CMAP}"       \
       --dpi        "${DPI}"        \
       --hold       "${HOLD}"       \
       --grid-res   "${GRID_RES}"; then
    ok_count=$((ok_count+1))
  else
    echo "    FAILED for SB_REF=${sb_ref}"; fail_count=$((fail_count+1))
  fi

done < "${MANIFEST_FILE}"

echo ""
echo "=== Done: ok=${ok_count}  skipped=${skip_count}  missing_meta=${missing_meta_count}  failed=${fail_count} ==="
