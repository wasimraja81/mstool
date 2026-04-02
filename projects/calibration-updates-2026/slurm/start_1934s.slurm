#! /bin/bash --login
#SBATCH --partition=askaprt
#SBATCH --time=24:00:00
#SBATCH --cluster=setonix
#SBATCH --ntasks=1
#SBATCH --ntasks-per-node=1
#SBATCH --job-name=POLCOMP-TESTS
#SBATCH --account=askaprt
#SBATCH --output=slurm-POLCOMP-TESTS-%j.out
#SBATCH --export=NONE

if [ -z "${BASH_VERSION:-}" ]; then
    exec /bin/bash "$0" "$@"
fi

for arg in "$@"; do
    if [[ "$arg" == "-h" || "$arg" == "--help" ]]; then
        cat <<'EOF'
Usage: start_1934s.slurm [options]

Options:
  --manifest <path>      Path to manifest file
  --start-index <idx>    Start tuple index (inclusive)
  --end-index <idx>      End tuple index (inclusive)
  --dry-run-parse        Print resolved tuple values and exit
  -h, --help             Show this help and exit
EOF
        exit 0
    fi
done

set -euo pipefail

# Setting up the environment
failure=false
echo "whoami: $(whoami)"
if [ "$(whoami)" == "" ]; then
    echo "ERROR - whoami not defined!"
    failure=true
fi
echo "HOME: ${HOME}"
if [ "${HOME}" == "" ]; then
    echo "ERROR - HOME not defined!"
    failure=true
fi
if [ "$failure" == "true" ]; then
   echo "Exiting as a failure"
   touch .pipeline-start
   exit 1
fi

unset ACES
unset PYTHONPATH
unset PYTHONSTARTUP

EARLY_DRY_RUN_PARSE=false
for arg in "$@"; do
    if [[ "$arg" == "--dry-run-parse" ]]; then
        EARLY_DRY_RUN_PARSE=true
        break
    fi
done

# Preserve submission directory before clearing SLURM_* environment.
# Under sbatch, $0 points to a spool copy (/var/spool/slurmd/...)
# so we cannot rely on dirname($0) to find repo-local templates.
SLURM_SUBMIT_DIR_SNAPSHOT="${SLURM_SUBMIT_DIR:-}"
for slurmEnvVar in $(env | grep SLURM_ | awk -F'=' '{print $1}'); do
    echo "Unsetting ${slurmEnvVar}..."
    unset $slurmEnvVar
done

if [[ "${EARLY_DRY_RUN_PARSE}" != "true" ]]; then
    module use /askapbuffer/payne/raj030/askaprtModules
    module load askappipeline/axa-3877-implement-q-correction-factors
    #module load askappipeline/axa-3859-fix-generate-parset-for-offset-fields
    #module load askappipeline/2.23.1
    #module load askappipeline/axa-3741-allow-general-processing-of-1934-fields
    #module load askappipeline/axa-3729-flag-bad-data-in-reference-tables
fi


DEFAULT_SB1934=77045
DEFAULT_HOLOSB=76554

SCRIPT_DIR=""
if [[ -n "${SLURM_SUBMIT_DIR_SNAPSHOT}" ]]; then
    # Walk upward from submit dir to locate the cloned repo root,
    # then pin SCRIPT_DIR to projects/calibration-updates-2026/slurm.
    search_dir="${SLURM_SUBMIT_DIR_SNAPSHOT}"
    while [[ "${search_dir}" != "/" ]]; do
        candidate="${search_dir}/projects/calibration-updates-2026/slurm"
        if [[ -f "${candidate}/run_1934Field.sh" ]]; then
            SCRIPT_DIR="${candidate}"
            break
        fi
        search_dir="$(cd "${search_dir}/.." && pwd)"
    done
fi

if [[ -z "${SCRIPT_DIR}" ]]; then
    # Fallback (works for direct shell execution, but under sbatch this
    # often resolves to /var/spool/slurmd/... and should be avoided).
    SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
fi

echo "INFO - SCRIPT_DIR: ${SCRIPT_DIR}"
MANIFEST_FILE_DEFAULT="${SCRIPT_DIR}/../manifests/manifest_ref_ws-4788.txt"
MANIFEST_FILE="${MANIFEST_FILE:-${MANIFEST_FILE_DEFAULT}}"
BSB_OVERRIDE="${BSB_OVERRIDE:-}"
ESB_OVERRIDE="${ESB_OVERRIDE:-}"
DRY_RUN_PARSE=false
EXPERIMENT=""

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
        --experiment)
            EXPERIMENT="$2"
            shift 2
            ;;
        --dry-run-parse)
            DRY_RUN_PARSE=true
            shift
            ;;
        *)
            echo "ERROR: Unknown argument '$1'"
            exit 1
            ;;
    esac
done

DIR_SB=/askapbuffer/payne/raj030/askap-scheduling-blocks

# WORK_DIR is set from HPC_BASE_DIR in the manifest; --experiment qcorr appends -qcorr at runtime.
EXPERIMENT="${EXPERIMENT:-baseline}"
WORK_DIR=""
SCIENCE_CONFIG_TEMPLATE="${SCRIPT_DIR}/run_1934Field.sh"
echo "INFO - SCIENCE_CONFIG_TEMPLATE: ${SCIENCE_CONFIG_TEMPLATE}"
if [[ ! -f "${SCIENCE_CONFIG_TEMPLATE}" ]]; then
    echo "ERROR: Missing 1934-field template: ${SCIENCE_CONFIG_TEMPLATE}"
    echo "ERROR: Ensure run_1934Field.sh exists in the slurm directory on HPC clone."
    exit 1
fi

#BP_UPDATE_MODIFY_AMP_STRATEGY="keep"
BP_UPDATE_MODIFY_AMP_STRATEGY="multiply"
DO_PREFLAG_REFTABLE=true
REQUIRE_STAGE1_PRODUCTS=true

refFieldList=(56572 \
	56644 \
	56647 \
	56500 \
	56721 \
	56667 \
	56669 \
	56868 \
	56374 \
	59068 \
	59072 \
	56474 \
        57235 \
        57239 \
	81082 81083 81084 81085 81086 \
	81099 81100 81104 81105 81098 \
	81138 81139 81140 81141 81142 81143 \
	81178 81180 81181 81182 81183 81184 \
	81185 81188 81189 81190 81191 81193 \
	81179 81192 \
	81202 81206 81207 81208 81209 81210)
# The following are 1934 bandpass observations that correspond to the 
# list of reference fields above: 
calFieldList=(56611 \
        56673 \
        56673 \
        56463 \
        56747 \
        56673 \
        56673 \
        56815 \
        56371 \
        59003 \
        59003 \
	56463 \
        57229 \
        57229 \
	81089 81089 81089 81089 81089 \
	81107 81107 81107 81107 81107 \
	81148 81148 81148 81148 81148 81148 \
	81195 81195 81195 81195 81195 81195 \
	81195 81195 81195 81195 81195 81195 \
	81195 81195 \
	81195 81195 81195 81195 81195 81195)

odcWeightList=(3611 \
	3611 \
	3611 \
	3611 \
	3611 \
	3611 \
	3611 \
	3611 \
	3611 \
	3616 \
	3616 \
	3611 \
	3611 \
	3611 \
	5229 5229 5229 5229 5229 \
	5231 5231 5231 5231 5231 \
	5233 5233 5233 5233 5233 5233 \
	5241 5241 5241 5241 5241 5241 \
	5241 5241 5241 5241 5241 5241 \
	5241 5241 \
	5241 5241 5241 5241 5241 5241)

sb1934List=()
holoSBList=()
ampStrategyList=()
doPreflagList=()

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

load_tuples_from_manifest() {
    local manifest_path="$1"
    local default_amp=""
    local default_do_preflag=""
    local default_odc=""

    [[ -f "${manifest_path}" ]] || { echo "ERROR: Manifest not found: ${manifest_path}"; exit 1; }

    refFieldList=()
    calFieldList=()
    odcWeightList=()
    sb1934List=()
    holoSBList=()
    ampStrategyList=()
    doPreflagList=()

    local line_no=0
    while IFS= read -r raw_line || [[ -n "${raw_line}" ]]; do
        line_no=$((line_no + 1))
        local line="${raw_line%%#*}"
        line="$(echo "${line}" | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//')"
        [[ -z "${line}" ]] && continue

        if [[ "${line}" =~ ^([A-Za-z_][A-Za-z0-9_]*)=(.+)$ ]]; then
            local cfg_key="${BASH_REMATCH[1]}"
            local cfg_val="${BASH_REMATCH[2]}"
            cfg_val="$(echo "${cfg_val}" | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//')"
            case "${cfg_key}" in
                HPC_BASE_DIR)
                    WORK_DIR="${cfg_val}"
                    ;;
                ODC_WEIGHT|ODC_WEIGHT_ID)
                    default_odc="$(strip_numeric_tag "${cfg_val}" "ODC-")"
                    if [[ -z "${default_odc}" ]]; then
                        echo "ERROR: Invalid global ODC value '${cfg_val}' on line ${line_no}"
                        exit 1
                    fi
                    ;;
                AMP_STRATEGY)
                    default_amp="${cfg_val}"
                    if [[ -z "${default_amp}" ]]; then
                        echo "ERROR: Empty AMP_STRATEGY on line ${line_no}"
                        exit 1
                    fi
                    ;;
                DO_PREFLAG_REFTABLE)
                    local normalized_do_preflag
                    normalized_do_preflag="$(normalize_do_preflag_value "${cfg_val}")"
                    if [[ -z "${normalized_do_preflag}" ]]; then
                        echo "ERROR: Invalid DO_PREFLAG_REFTABLE value '${cfg_val}' on line ${line_no}; expected true/false"
                        exit 1
                    fi
                    default_do_preflag="${normalized_do_preflag}"
                    ;;
            esac
            continue
        fi

        line="${line//,/ }"
        local -a cols
        read -r -a cols <<< "${line}"
        if [[ ${#cols[@]} -eq 0 ]]; then
            continue
        fi

        # Optional leading row index:
        # idx sb_ref sb_1934 sb_holo sb_target_1934 [optional KEY=VALUE tokens]
        if [[ "${cols[0]}" =~ ^[0-9]+$ ]]; then
            cols=("${cols[@]:1}")
        fi

        local col1="${cols[0]:-}" col2="${cols[1]:-}" col3="${cols[2]:-}" col4="${cols[3]:-}"
        local -a opt_tokens=()
        if [[ ${#cols[@]} -gt 4 ]]; then
            opt_tokens=("${cols[@]:4}")
        fi

        local col1_lc
        col1_lc="$(echo "${col1}" | tr '[:upper:]' '[:lower:]')"
        if [[ "${col1_lc}" == "sb_ref" || "${col1_lc}" == "sbref" ]]; then
            continue
        fi

        if [[ -z "${col1}" || -z "${col2}" || -z "${col3}" || -z "${col4}" ]]; then
            echo "WARNING: Skipping manifest line ${line_no} (expected at least 4 columns: [idx] sb_ref sb_1934 sb_holo sb_target_1934 [optional KEY=VALUE tokens])"
            continue
        fi

        local sb_ref_now sb_1934_now sb_holo_now sb_target_now
        sb_ref_now="$(strip_numeric_tag "${col1}" "SB_REF-")"
        sb_1934_now="$(strip_numeric_tag "${col2}" "SB_1934-")"
        sb_holo_now="$(strip_numeric_tag "${col3}" "SB_HOLO-")"
        sb_target_now="$(strip_numeric_tag "${col4}" "SB_TARGET_1934-")"

        if [[ -z "${sb_ref_now}" || -z "${sb_1934_now}" || -z "${sb_holo_now}" || -z "${sb_target_now}" ]]; then
            echo "WARNING: Skipping manifest line ${line_no} (invalid SB tags)"
            continue
        fi

        local row_odc="${default_odc}"
        local row_amp="${default_amp}"
        local row_do_preflag="${default_do_preflag}"
        local token token_key token_val normalized_row_do_preflag
        for token in "${opt_tokens[@]}"; do
            [[ -z "${token}" ]] && continue
            if [[ "${token}" =~ ^([A-Za-z_][A-Za-z0-9_]*)=(.+)$ ]]; then
                token_key="${BASH_REMATCH[1]}"
                token_val="${BASH_REMATCH[2]}"
                case "${token_key}" in
                    ODC_WEIGHT|ODC_WEIGHT_ID)
                        row_odc="$(strip_numeric_tag "${token_val}" "ODC-")"
                        if [[ -z "${row_odc}" ]]; then
                            echo "ERROR: Invalid ODC token '${token}' on line ${line_no}"
                            exit 1
                        fi
                        ;;
                    AMP_STRATEGY)
                        row_amp="${token_val}"
                        if [[ -z "${row_amp}" ]]; then
                            echo "ERROR: Empty AMP_STRATEGY token '${token}' on line ${line_no}"
                            exit 1
                        fi
                        ;;
                    DO_PREFLAG_REFTABLE)
                        normalized_row_do_preflag="$(normalize_do_preflag_value "${token_val}")"
                        if [[ -z "${normalized_row_do_preflag}" ]]; then
                            echo "ERROR: Invalid DO_PREFLAG_REFTABLE token '${token}' on line ${line_no}"
                            exit 1
                        fi
                        row_do_preflag="${normalized_row_do_preflag}"
                        ;;
                    REF_FIELDNAME)
                        ;;
                    *)
                        echo "ERROR: Unknown optional token '${token}' on line ${line_no}"
                        exit 1
                        ;;
                esac
            else
                echo "ERROR: Non key=value optional token '${token}' on line ${line_no}"
                exit 1
            fi
        done

        if [[ -z "${row_odc}" ]]; then
            echo "ERROR: Missing ODC weight for tuple on line ${line_no} (set ODC_WEIGHT globally or per-row)"
            exit 1
        fi
        if [[ -z "${row_amp}" ]]; then
            echo "ERROR: Missing AMP_STRATEGY for tuple on line ${line_no} (set AMP_STRATEGY globally or per-row)"
            exit 1
        fi
        if [[ -z "${row_do_preflag}" ]]; then
            echo "ERROR: Missing DO_PREFLAG_REFTABLE for tuple on line ${line_no} (set DO_PREFLAG_REFTABLE globally or per-row)"
            exit 1
        fi

        refFieldList+=("${sb_ref_now}")
        calFieldList+=("${sb_target_now}")
        odcWeightList+=("${row_odc}")
        sb1934List+=("${sb_1934_now}")
        holoSBList+=("${sb_holo_now}")
        ampStrategyList+=("${row_amp}")
        doPreflagList+=("${row_do_preflag}")
    done < "${manifest_path}"

    if [[ ${#refFieldList[@]} -eq 0 ]]; then
        echo "ERROR: No valid tuples loaded from manifest: ${manifest_path}"
        exit 1
    fi
}

if [[ -f "${MANIFEST_FILE}" ]]; then
    echo "INFO - Loading tuples from manifest: ${MANIFEST_FILE}"
    load_tuples_from_manifest "${MANIFEST_FILE}"
    if [[ -z "${WORK_DIR}" ]]; then
        echo "ERROR - HPC_BASE_DIR is not set in manifest (${MANIFEST_FILE})."
        echo "        Add: HPC_BASE_DIR=/scratch/.../your_work_dir"
        exit 1
    fi
    [[ "${EXPERIMENT}" == "qcorr" ]] && WORK_DIR="${WORK_DIR}-qcorr"
    echo "INFO - EXPERIMENT=${EXPERIMENT}; WORK_DIR=${WORK_DIR}"
    mkdir -p "${WORK_DIR}/manifest_archive"
    cp "${MANIFEST_FILE}" "${WORK_DIR}/manifest_archive/$(basename "${MANIFEST_FILE}" .txt).$(date +%Y%m%dT%H%M%S).txt"
    echo "INFO - Manifest snapshot saved to ${WORK_DIR}/manifest_archive/"
else
    echo "ERROR - Manifest not found (${MANIFEST_FILE}); strict strategy mode requires an explicit manifest"
    exit 1
fi

nSBref=${#refFieldList[@]}
nSBcal=${#calFieldList[@]}
nWeights=${#odcWeightList[@]}

if [ "${nSBref}" != "${nSBcal}" ];then
    echo "ERROR - Number of calFields(${nSBcal}) != number of referenceFields (${nSBref})"
    exit 1
fi
if [ "${nSBref}" != "${nWeights}" ];then
    echo "ERROR - Number of Fields(${nSBcal}) != number of Weights (${nWeights})"
    exit 1
fi

echo "INFO - Total number of Reference-1934 pairs found with valid Weight IDs: ${nSBref} "

# Step-1: Fetch the data
bSB=${BSB_OVERRIDE:-0}
eSB=${ESB_OVERRIDE:-$((${nSBref} - 1))}
#eSB=$((${nSBref} - 1))

if [[ ${bSB} -lt 0 || ${eSB} -ge ${nSBref} || ${bSB} -gt ${eSB} ]]; then
    echo "ERROR - Invalid start/end indices: bSB=${bSB}, eSB=${eSB}, tuple_count=${nSBref}"
    exit 1
fi

if [[ "${DRY_RUN_PARSE}" == "true" ]]; then
    echo "INFO - Dry-run parse mode (no processing)"
    echo "INFO - Manifest: ${MANIFEST_FILE}"
    echo "INFO - Index range: ${bSB}..${eSB}"
    for (( iSB=${bSB}; iSB<=${eSB}; iSB++ )); do
        echo "IDX=${iSB} SB_REF=${refFieldList[${iSB}]} SB_1934=${sb1934List[${iSB}]} SB_HOLO=${holoSBList[${iSB}]} SB_TARGET_1934=${calFieldList[${iSB}]} ODC_WEIGHT=${odcWeightList[${iSB}]} AMP_STRATEGY=${ampStrategyList[${iSB}]} DO_PREFLAG_REFTABLE=${doPreflagList[${iSB}]}"
    done
    exit 0
fi

nSB=$((${eSB} - ${bSB} + 1))

echo "INFO - We will process a total of ${nSB} 1934-638 bandpass SBIDs"
bField=0
eField=35

for (( iSB=${bSB}; iSB<=${eSB}; iSB++ ))
do
    sbRefNow=${refFieldList[${iSB}]}
    sbCalNow=${calFieldList[${iSB}]}
    sb1934Now=${sb1934List[${iSB}]}
    holoSBNow=${holoSBList[${iSB}]}
    ampStrategyNow=${ampStrategyList[${iSB}]}
    doPreflagNow=${doPreflagList[${iSB}]}
    odcWeightNow=${odcWeightList[${iSB}]}
    strategySuffixNow=""
    if [ "${ampStrategyNow}" != "" ]; then
        strategySuffixNow="${strategySuffixNow}_AMP_STRATEGY-${ampStrategyNow}"
    fi
    if [ "${doPreflagNow}" == "true" ]; then
        strategySuffixNow="${strategySuffixNow}-insituPreflags"
    fi
    echo "INFO - Processing SB number: ${iSB} of ${nSB}"
    if [ -e ${DIR_SB}/${sbRefNow} ] && [ -e ${DIR_SB}/${sbCalNow} ];then
        tupleProcessingDir=${WORK_DIR}/ODC-${odcWeightNow}/SB_REF-${sbRefNow}_SB_1934-${sb1934Now}_SB_HOLO-${holoSBNow}${strategySuffixNow}
    scienceProcessingDir="${tupleProcessingDir}/1934-processing-SB-${sbCalNow}"

        if [ "${REQUIRE_STAGE1_PRODUCTS}" == "true" ]; then
            expectedBandpassTable="${tupleProcessingDir}/BPCAL/calparameters.1934_bp.SB${sbRefNow}.tab"
            expectedLeakageTable="${tupleProcessingDir}/BPCAL/calparameters.1934_bpleakage.SB${sbRefNow}.tab"

            missingStage1=0
            if [[ ! -e "${expectedBandpassTable}" ]]; then
                echo "ERROR: Missing bandpass table: ${expectedBandpassTable}"
                missingStage1=1
            fi
            if [[ ! -e "${expectedLeakageTable}" ]]; then
                echo "ERROR: Missing leakage table: ${expectedLeakageTable}"
                missingStage1=1
            fi

            if [[ ${missingStage1} -eq 1 ]]; then
                echo "ERROR: Stage-1 products unavailable for tuple index ${iSB}."
                echo "ERROR: Expected stage-1 products under: ${tupleProcessingDir}/BPCAL/"
                exit 1
            fi
        fi

    mkdir -p ${scienceProcessingDir}

	# Process beam-N of field-N for the 1934 datasets: 
    # Processing for manifest-selected holography SB
        echo "INFO - Processing SB_1934 ${sbCalNow} using reference field ${sbRefNow}, old 1934 ${sb1934Now}, SB_PB: ${holoSBNow}"
    echo "INFO - Processing dir1: ${scienceProcessingDir}"
	echo " "
	for (( iField=${bField}; iField<=${eField}; iField++ ))
        do
            cd ${scienceProcessingDir}
            FIELD_NOW="B1934-638_beam${iField}"
            configNow1="run_Field_${FIELD_NOW}.sh"
            mkdir -p "${FIELD_NOW}"
            cd ${FIELD_NOW}
            cat "${SCIENCE_CONFIG_TEMPLATE}" >"${configNow1}"
            cat >> "${configNow1}" <<EOF
FIELD_SELECTION_SCIENCE="${FIELD_NOW}"
SUBMIT_JOBS=true
# We will image only beam-${iField} for field-${iField}
BEAMLIST="${iField}"
DO_CONTCUBE_IMAGING=false
DO_VALIDATION_POSSUM=false
DO_CONVOLVE_CONT=false
TABLE_BANDPASS=${tupleProcessingDir}/BPCAL/calparameters.1934_bp.SB${sbRefNow}.tab
TABLE_LEAKAGE=${tupleProcessingDir}/BPCAL/calparameters.1934_bpleakage.SB${sbRefNow}.tab
DIR_SB=${DIR_SB}
BP_UPDATE_MODIFY_AMP_STRATEGY=${ampStrategyNow}
DO_RAPID_SURVEY=true
DO_MOSAIC=false
DO_ALT_IMAGER_CONT=false
NUM_CORES_CONTIMG_SCI=4
USE_PARALLEL_WRITE_MS=false
EOF
            processASKAP.sh -s ${sbCalNow} -b ${sbRefNow} -p ${holoSBNow} -t "${configNow1}"
        done
    fi
done
