#! /bin/bash --login
set -euo pipefail

if command -v module >/dev/null 2>&1; then
    module load singularity/4.1.0-askap
    module use /askapbuffer/payne/raj030/askaprtModules
    module load askappy/2.9.1
fi

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SEARCH_DIR="${SCRIPT_DIR}"
REPO_ROOT=""
while [[ "${SEARCH_DIR}" != "/" ]]; do
    if [[ -f "${SEARCH_DIR}/setup.py" && -f "${SEARCH_DIR}/mstool/bin/averageMS.py" ]]; then
        REPO_ROOT="${SEARCH_DIR}"
        break
    fi
    SEARCH_DIR="$(cd "${SEARCH_DIR}/.." && pwd)"
done

if [[ -z "${REPO_ROOT}" ]]; then
    echo "ERROR: Could not locate repo root containing setup.py and mstool/bin/averageMS.py"
    exit 1
fi

AVERAGE_MS_SCRIPT="${REPO_ROOT}/mstool/bin/averageMS.py"
MANIFEST_FILE_DEFAULT="${SCRIPT_DIR}/../manifests/sb_manifest_reffield_average.txt"
MANIFEST_FILE="${MANIFEST_FILE:-${MANIFEST_FILE_DEFAULT}}"
BSB_OVERRIDE="${BSB_OVERRIDE:-}"
ESB_OVERRIDE="${ESB_OVERRIDE:-}"
BEAM_START="${BEAM_START:-0}"
BEAM_END="${BEAM_END:-35}"
DRY_RUN="false"

DIR_SB=/askapbuffer/payne/raj030/askap-scheduling-blocks
# WORK_DIR is set from HPC_BASE_DIR in the manifest (last used: assess_1934-2026-qcorr).
WORK_DIR=""
BP_UPDATE_MODIFY_AMP_STRATEGY="multiply"
DO_PREFLAG_REFTABLE="true"

refFieldList=()
calFieldList=()
odcWeightList=()
sb1934List=()
holoSBList=()
ampStrategyList=()
doPreflagList=()
fieldNameList=()

usage() {
    cat <<EOF
Usage:
  assess_possum_1934s.sh [options]

Options:
  --manifest FILE        Path to tuple manifest (default: ${MANIFEST_FILE_DEFAULT})
  --start-index N        Start tuple index (0-based)
  --end-index N          End tuple index (0-based)
  --beam-start N         Start beam index (default: 0)
  --beam-end N           End beam index (default: 35)
    --dry-run              Print planned actions without running averageMS.py
  -h, --help             Show this help
EOF
}

trim_whitespace() {
        echo "$1" | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//'
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --manifest)
            MANIFEST_FILE="$2"
            shift 2
            ;;
        --start-index)
            BSB_OVERRIDE="$2"
            shift 2
            ;;
        --end-index)
            ESB_OVERRIDE="$2"
            shift 2
            ;;
        --beam-start)
            BEAM_START="$2"
            shift 2
            ;;
        --beam-end)
            BEAM_END="$2"
            shift 2
            ;;
        --dry-run)
            DRY_RUN="true"
            shift
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

strip_numeric_tag() {
    local value="$1"
    local prefix="$2"
    if [[ "${value}" =~ ^${prefix}([0-9]+)$ ]]; then
        echo "${BASH_REMATCH[1]}"
    elif [[ "${value}" =~ ^[0-9]+$ ]]; then
        echo "${value}"
    else
        echo ""
    fi
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

resolve_field_name_from_schedblock() {
    local sb_ref_now="$1"
    [[ -n "${sb_ref_now}" ]] || { echo ""; return; }
    command -v schedblock >/dev/null 2>&1 || { echo ""; return; }

    local info_output
    info_output="$(schedblock info -p "${sb_ref_now}" 2>/dev/null || true)"
    [[ -n "${info_output}" ]] || { echo ""; return; }

    local targets_line targets_raw
    targets_line="$(echo "${info_output}" | grep -E '^common\.targets[[:space:]]*=' | tail -n 1 || true)"
    [[ -n "${targets_line}" ]] || { echo ""; return; }

    targets_raw="$(echo "${targets_line}" | sed -E 's/^[^=]*=[[:space:]]*\[(.*)\][[:space:]]*$/\1/')"
    targets_raw="$(trim_whitespace "${targets_raw}")"
    [[ -n "${targets_raw}" ]] || { echo ""; return; }

    local IFS=','
    local target_tokens=()
    read -r -a target_tokens <<< "${targets_raw}"

    local cleaned_targets=()
    local t
    for t in "${target_tokens[@]}"; do
        t="$(trim_whitespace "${t}")"
        [[ -n "${t}" ]] && cleaned_targets+=("${t}")
    done

    if [[ ${#cleaned_targets[@]} -eq 0 ]]; then
        echo ""
        return
    fi

    if [[ ${#cleaned_targets[@]} -gt 1 ]]; then
        echo "WARNING: Multiple targets found for SB_REF=${sb_ref_now} (${cleaned_targets[*]}). Using REF_FIELDNAME=Multi." >&2
        echo "Multi"
        return
    fi

    local selected_target="${cleaned_targets[0]}"
    local field_line
    field_line="$(echo "${info_output}" | grep -E "^common\.target\.${selected_target//./\.}\.field_name[[:space:]]*=" | head -n 1 || true)"
    if [[ -z "${field_line}" ]]; then
        echo ""
        return
    fi

    echo "$(echo "${field_line}" | sed -E 's/^[^=]*=[[:space:]]*//' | sed -E 's/[[:space:]]+$//')"
}

load_tuples_from_manifest() {
    local manifest_path="$1"
    local default_amp="${BP_UPDATE_MODIFY_AMP_STRATEGY}"
    local default_do_preflag="${DO_PREFLAG_REFTABLE}"
    local default_odc=""
    local default_field_name=""

    [[ -f "${manifest_path}" ]] || { echo "ERROR: Manifest not found: ${manifest_path}"; exit 1; }

    refFieldList=()
    calFieldList=()
    odcWeightList=()
    sb1934List=()
    holoSBList=()
    ampStrategyList=()
    doPreflagList=()
    fieldNameList=()

    local line_no=0
    while IFS= read -r raw_line || [[ -n "${raw_line}" ]]; do
        line_no=$((line_no + 1))
        local line="${raw_line%%#*}"
        line="$(echo "${line}" | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//')"
        [[ -z "${line}" ]] && continue

        if [[ "${line}" =~ ^([A-Za-z_][A-Za-z0-9_]*)=(.+)$ ]]; then
            local cfg_key="${BASH_REMATCH[1]}"
            local cfg_val="${BASH_REMATCH[2]}"
            cfg_val="$(trim_whitespace "${cfg_val}")"
            case "${cfg_key}" in
                HPC_BASE_DIR)
                    WORK_DIR="${cfg_val}"
                    ;;
                ODC_WEIGHT_ID|ODC|WEIGHT_ID)
                    default_odc="$(strip_numeric_tag "${cfg_val}" "ODC-")"
                    ;;
                AMP_STRATEGY)
                    default_amp="${cfg_val}"
                    ;;
                DO_PREFLAG_REFTABLE|PREFLAGGING_STRATEGY|PREFLAG_STRATEGY|FLAG_STRATEGY)
                    local normalized_do_preflag
                    normalized_do_preflag="$(normalize_do_preflag_value "${cfg_val}")"
                    if [[ -n "${normalized_do_preflag}" ]]; then
                        default_do_preflag="${normalized_do_preflag}"
                    fi
                    ;;
                REF_FIELDNAME)
                    default_field_name="$(normalize_field_name_token "${cfg_val}")"
                    ;;
            esac
            continue
        fi

        line="${line//,/ }"
        local col1="" col2="" col3="" col4="" col5="" col6="" col7="" col8="" extra=""
        read -r col1 col2 col3 col4 col5 col6 col7 col8 extra <<< "${line}"

        if [[ "${col1}" =~ ^[0-9]+$ ]]; then
            col1="${col2}"
            col2="${col3}"
            col3="${col4}"
            col4="${col5}"
            col5="${col6}"
            col6="${col7}"
            col7="${col8}"
            col8="${extra}"
            extra=""
        fi

        local col1_lc
        col1_lc="$(echo "${col1}" | tr '[:upper:]' '[:lower:]')"
        if [[ "${col1_lc}" == "sb_ref" || "${col1_lc}" == "sbref" ]]; then
            continue
        fi

        if [[ -z "${col1}" || -z "${col2}" || -z "${col3}" || -z "${col4}" || -n "${extra}" ]]; then
            echo "WARNING: Skipping manifest line ${line_no}: malformed row"
            continue
        fi

        local sb_ref_now sb_1934_now sb_holo_now sb_target_now
        sb_ref_now="$(strip_numeric_tag "${col1}" "SB_REF-")"
        sb_1934_now="$(strip_numeric_tag "${col2}" "SB_1934-")"
        sb_holo_now="$(strip_numeric_tag "${col3}" "SB_HOLO-")"
        sb_target_now="$(strip_numeric_tag "${col4}" "SB_TARGET_1934-")"

        if [[ -z "${sb_ref_now}" || -z "${sb_1934_now}" || -z "${sb_holo_now}" || -z "${sb_target_now}" ]]; then
            echo "WARNING: Skipping manifest line ${line_no}: invalid SB tags"
            continue
        fi

        local row_odc="${default_odc}"
        local row_amp="${default_amp}"
        local row_do_preflag="${default_do_preflag}"
        local row_field_name="${default_field_name}"
        local token
        for token in "${col5}" "${col6}" "${col7}" "${col8}"; do
            [[ -z "${token}" ]] && continue
            if [[ "${token}" =~ ^([A-Za-z_][A-Za-z0-9_-]*)=(.+)$ ]]; then
                local token_key token_val normalized_key normalized_pref
                token_key="${BASH_REMATCH[1]}"
                token_val="${BASH_REMATCH[2]}"
                token_val="$(trim_whitespace "${token_val}")"
                normalized_key="$(normalize_manifest_key "${token_key}")"
                case "${normalized_key}" in
                    ODC_WEIGHT|ODC_WEIGHT_ID|ODC|WEIGHT_ID)
                        row_odc="$(strip_numeric_tag "${token_val}" "ODC-")"
                        ;;
                    AMP_STRATEGY)
                        row_amp="${token_val}"
                        ;;
                    DO_PREFLAG_REFTABLE|DO_PREFLAG|PREFLAGGING_STRATEGY|PREFLAG_STRATEGY|FLAG_STRATEGY)
                        normalized_pref="$(normalize_do_preflag_value "${token_val}")"
                        [[ -n "${normalized_pref}" ]] || { echo "WARNING: invalid do_preflag token at line ${line_no}"; continue 2; }
                        row_do_preflag="${normalized_pref}"
                        ;;
                    REF_FIELDNAME)
                        row_field_name="$(normalize_field_name_token "REF_FIELDNAME=${token_val}")"
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

        [[ -n "${row_odc}" ]] || { echo "WARNING: missing ODC at line ${line_no}"; continue; }

        refFieldList+=("${sb_ref_now}")
        calFieldList+=("${sb_target_now}")
        odcWeightList+=("${row_odc}")
        sb1934List+=("${sb_1934_now}")
        holoSBList+=("${sb_holo_now}")
        ampStrategyList+=("${row_amp}")
        doPreflagList+=("${row_do_preflag}")
        fieldNameList+=("${row_field_name}")
    done < "${manifest_path}"

    if [[ ${#refFieldList[@]} -eq 0 ]]; then
        echo "ERROR: No valid tuples loaded from manifest: ${manifest_path}"
        exit 1
    fi
}

load_tuples_from_manifest "${MANIFEST_FILE}"
if [[ -z "${WORK_DIR}" ]]; then
    echo "ERROR - HPC_BASE_DIR is not set in manifest (${MANIFEST_FILE})."
    echo "        Add: HPC_BASE_DIR=/scratch/.../your_work_dir"
    exit 1
fi
mkdir -p "${WORK_DIR}/manifest_archive"
cp "${MANIFEST_FILE}" "${WORK_DIR}/manifest_archive/$(basename "${MANIFEST_FILE}" .txt).$(date +%Y%m%dT%H%M%S).txt"
echo "INFO - Manifest snapshot saved to ${WORK_DIR}/manifest_archive/"

nSBref=${#refFieldList[@]}
nSBcal=${#calFieldList[@]}
nWeights=${#odcWeightList[@]}
if [[ "${nSBref}" != "${nSBcal}" || "${nSBref}" != "${nWeights}" || "${nSBref}" != "${#fieldNameList[@]}" ]]; then
    echo "ERROR - Manifest tuple arrays are inconsistent"
    exit 1
fi

bSB=${BSB_OVERRIDE:-0}
eSB=${ESB_OVERRIDE:-$((nSBref - 1))}
if [[ ${bSB} -lt 0 || ${eSB} -ge ${nSBref} || ${bSB} -gt ${eSB} ]]; then
    echo "ERROR - Invalid start/end indices: bSB=${bSB}, eSB=${eSB}, tuple_count=${nSBref}"
    exit 1
fi
if [[ ${BEAM_START} -lt 0 || ${BEAM_END} -lt ${BEAM_START} ]]; then
    echo "ERROR - Invalid beam range: ${BEAM_START}-${BEAM_END}"
    exit 1
fi

echo "INFO - Manifest: ${MANIFEST_FILE}"
echo "INFO - averageMS script: ${AVERAGE_MS_SCRIPT}"
echo "INFO - Tuple index range: ${bSB}..${eSB}"
echo "INFO - Beam range: ${BEAM_START}..${BEAM_END}"
echo "INFO - Dry run: ${DRY_RUN}"

for (( iSB=${bSB}; iSB<=${eSB}; iSB++ )); do
    sbRefNow=${refFieldList[${iSB}]}
    sbCalNow=${calFieldList[${iSB}]}
    sb1934Now=${sb1934List[${iSB}]}
    holoSBNow=${holoSBList[${iSB}]}
    ampStrategyNow=${ampStrategyList[${iSB}]}
    doPreflagNow=${doPreflagList[${iSB}]}
    odcWeightNow=${odcWeightList[${iSB}]}
    fieldNameNow="$(trim_whitespace "${fieldNameList[${iSB}]}")"
    if [[ -z "${fieldNameNow}" ]]; then
        fieldNameNow="$(resolve_field_name_from_schedblock "${sbRefNow}")"
    fi

    strategySuffixNow=""
    if [[ -n "${ampStrategyNow}" ]]; then
        strategySuffixNow="${strategySuffixNow}_AMP_STRATEGY-${ampStrategyNow}"
    fi
    if [[ "${doPreflagNow}" == "true" ]]; then
        strategySuffixNow="${strategySuffixNow}-insituPreflags"
    fi

    tupleProcessingDir="${WORK_DIR}/ODC-${odcWeightNow}/SB_REF-${sbRefNow}_SB_1934-${sb1934Now}_SB_HOLO-${holoSBNow}${strategySuffixNow}"
    scienceProcessingDir="${tupleProcessingDir}/1934-processing-SB-${sbCalNow}"
    plotDir="${scienceProcessingDir}/assessment_results"

    echo "INFO - Tuple index ${iSB}: ref=${sbRefNow} target=${sbCalNow} odc=${odcWeightNow}"

    if [[ ! -e "${DIR_SB}/${sbRefNow}" || ! -e "${DIR_SB}/${sbCalNow}" ]]; then
        echo "WARNING: Skipping tuple ${iSB} because SB dirs are missing in ${DIR_SB}"
        continue
    fi

    if [[ "${DRY_RUN}" == "true" ]]; then
        echo "DRY-RUN: mkdir -p ${plotDir}"
    else
        mkdir -p "${plotDir}"
    fi

    if [[ ! -d "${scienceProcessingDir}" ]]; then
        echo "WARNING: Missing science processing directory: ${scienceProcessingDir}"
        continue
    fi

    cd "${scienceProcessingDir}"

    for (( iBeam=${BEAM_START}; iBeam<=${BEAM_END}; iBeam++ )); do
        printf -v beamNow "%02d" $((10#${iBeam}))
        fieldNow="B1934-638_beam${iBeam}"

        msNow="${fieldNow}/${fieldNow}/scienceData.Bandpass_closepack36_920MHz_0.9_1MHz.SB${sbCalNow}.${fieldNow}.beam${beamNow}.ms"
        outFileNow="${plotDir}/scienceData.Bandpass_closepack36_920MHz_0.9_1MHz.SB${sbCalNow}.${fieldNow}.beam${beamNow}.txt"
        plotFileNow="${plotDir}/scienceData.Bandpass_closepack36_920MHz_0.9_1MHz.SB${sbCalNow}.${fieldNow}.beam${beamNow}.png"

        msNowLeakageCal="${fieldNow}/${fieldNow}/scienceData.Bandpass_closepack36_920MHz_0.9_1MHz.SB${sbCalNow}.${fieldNow}.beam${beamNow}_averaged_cal.leakage.ms"
        outFileNowLeakageCal="${plotDir}/scienceData.Bandpass_closepack36_920MHz_0.9_1MHz.SB${sbCalNow}.${fieldNow}.beam${beamNow}.lcal.txt"
        plotFileNowLeakageCal="${plotDir}/scienceData.Bandpass_closepack36_920MHz_0.9_1MHz.SB${sbCalNow}.${fieldNow}.beam${beamNow}.lcal.png"

        echo "INFO - Assessing tuple ${iSB}, beam ${beamNow}, field ${fieldNow}"

        if [[ -e "${msNow}" ]]; then
            if [[ "${DRY_RUN}" == "true" ]]; then
                echo "DRY-RUN: python ${AVERAGE_MS_SCRIPT} -i ${msNow} -o ${outFileNow} -t 0 -f 1 -p stokes -a1 -1 --plot-output ${plotFileNow} --ylim-pol -5 +5 --sb-ref ${sbRefNow} --sb-1934 ${sb1934Now} --sb-holo ${holoSBNow} --sb-target-1934 ${sbCalNow} --field-name ${fieldNameNow}"
            else
                python "${AVERAGE_MS_SCRIPT}" -i "${msNow}" -o "${outFileNow}" -t 0 -f 1 -p stokes -a1 -1 --plot-output "${plotFileNow}" --ylim-pol -5 +5 --sb-ref "${sbRefNow}" --sb-1934 "${sb1934Now}" --sb-holo "${holoSBNow}" --sb-target-1934 "${sbCalNow}" --field-name "${fieldNameNow}"
            fi
        else
            echo "WARNING: Missing msdata ${msNow}"
        fi

        if [[ -e "${msNowLeakageCal}" ]]; then
            if [[ "${DRY_RUN}" == "true" ]]; then
                echo "DRY-RUN: python ${AVERAGE_MS_SCRIPT} -i ${msNowLeakageCal} -o ${outFileNowLeakageCal} -t 0 -f 1 -p stokes -a1 -1 --plot-output ${plotFileNowLeakageCal} --ylim-pol -5 +5 --sb-ref ${sbRefNow} --sb-1934 ${sb1934Now} --sb-holo ${holoSBNow} --sb-target-1934 ${sbCalNow} --field-name ${fieldNameNow}"
            else
                python "${AVERAGE_MS_SCRIPT}" -i "${msNowLeakageCal}" -o "${outFileNowLeakageCal}" -t 0 -f 1 -p stokes -a1 -1 --plot-output "${plotFileNowLeakageCal}" --ylim-pol -5 +5 --sb-ref "${sbRefNow}" --sb-1934 "${sb1934Now}" --sb-holo "${holoSBNow}" --sb-target-1934 "${sbCalNow}" --field-name "${fieldNameNow}"
            fi
        else
            echo "WARNING: Missing msdata ${msNowLeakageCal}"
        fi
    done
done
