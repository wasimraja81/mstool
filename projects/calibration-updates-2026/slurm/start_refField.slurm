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
Usage: start_refField.slurm [options]

Options:
  --manifest <path>             Path to manifest file
  --start-index <idx>           Start tuple index (inclusive)
  --end-index <idx>             End tuple index (inclusive)
  --experiment <baseline|qcorr>  Experiment type: drives Q-corrections and HPC output path
  --q-corr-csv <path>            Override Q-correction CSV (auto-derived from manifest cohort for qcorr)
  --q-corr-variant <val>         CSV variant column: bpcal or lcal (default: bpcal)
  --q-corr-ref-ws <val>          Override ref_ws for CSV row selection (default: from pipeline metadata)
  --q-corr-allow-mismatch <bool> Allow ref_ws mismatch (true/false, default: false)
  --dry-run-parse                Print resolved tuple values and exit
  -h, --help                     Show this help and exit
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
    #module load askappipeline/axa-3729-flag-bad-data-in-reference-tables
fi

DO_FIND_BANDPASS=true
DO_FETCH_RAWDATA=true

SCRIPT_DIR=""
if [[ -n "${SLURM_SUBMIT_DIR_SNAPSHOT}" ]]; then
    # Walk upward from submit dir to locate the cloned repo root,
    # then pin SCRIPT_DIR to projects/calibration-updates-2026/slurm.
    search_dir="${SLURM_SUBMIT_DIR_SNAPSHOT}"
    while [[ "${search_dir}" != "/" ]]; do
        candidate="${search_dir}/projects/calibration-updates-2026/slurm"
        if [[ -f "${candidate}/run_refField.sh" ]]; then
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
Q_CORR_CSV=""
Q_CORR_CSV_EXPLICIT=0
Q_CORR_VARIANT="bpcal"
Q_CORR_REF_WS=""
Q_CORR_ALLOW_MISMATCH="false"

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
        --q-corr-csv)
            Q_CORR_CSV="$2"
            Q_CORR_CSV_EXPLICIT=1
            shift 2
            ;;
        --q-corr-variant)
            Q_CORR_VARIANT="$2"
            shift 2
            ;;
        --q-corr-ref-ws)
            Q_CORR_REF_WS="$2"
            shift 2
            ;;
        --q-corr-allow-mismatch)
            Q_CORR_ALLOW_MISMATCH="$2"
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

BP_UPDATE_MODIFY_AMP_STRATEGY=multiply
#BP_UPDATE_MODIFY_AMP_STRATEGY=""
DO_PREFLAG_REFTABLE=true

DEFAULT_SB1934=77045
DEFAULT_HOLOSB=76554
DIR_SB=/askapbuffer/payne/raj030/askap-scheduling-blocks
if [[ "${EARLY_DRY_RUN_PARSE}" != "true" ]]; then
    mkdir -p ${DIR_SB}
fi

# WORK_DIR is set from HPC_BASE_DIR in the manifest; --experiment qcorr appends -qcorr at runtime.
EXPERIMENT="${EXPERIMENT:-baseline}"
WORK_DIR=""
FETCHED_DIR="/askapbuffer/payne/dmitchell/askap-scheduling-blocks"
#FETCHED_DIR="/scratch/askaprt/tgalvin/racs_low3"
REF_CONFIG_TEMPLATE="${SCRIPT_DIR}/run_refField.sh"
echo "INFO - REF_CONFIG_TEMPLATE: ${REF_CONFIG_TEMPLATE}"
if [[ ! -f "${REF_CONFIG_TEMPLATE}" ]]; then
    echo "ERROR: Missing reference-field template: ${REF_CONFIG_TEMPLATE}"
    echo "ERROR: Ensure run_refField.sh exists in the slurm directory on HPC clone."
    exit 1
fi
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
    # Derive APPLY_Q_CORRECTIONS and validate Q_CORR_CSV from --experiment.
    if [[ "${EXPERIMENT}" == "qcorr" ]]; then
        APPLY_Q_CORRECTIONS="true"
        if [[ ${Q_CORR_CSV_EXPLICIT} -eq 0 ]]; then
            _cohort_id="$(basename "${MANIFEST_FILE}" .txt | sed 's/^manifest_//')"
            Q_CORR_CSV="/askapbuffer/payne/raj030/askap-calibration-updates/${_cohort_id}/dq_du_correction_factors.csv"
        fi
        if [[ ! -f "${Q_CORR_CSV}" ]]; then
            echo "ERROR ================================================================"
            echo "ERROR  Q-correction CSV not found for --experiment qcorr:"
            echo "ERROR    ${Q_CORR_CSV}"
            echo "ERROR  Complete the baseline pipeline first, then copy the output:"
            echo "ERROR    cp <LOCAL_BASE>/plots/dq_du_correction_factors.csv \\"
            echo "ERROR       $(dirname \"${Q_CORR_CSV}\")/"
            echo "ERROR ================================================================"
            exit 1
        fi
        echo "INFO - Q_CORR_CSV=${Q_CORR_CSV}"
    else
        APPLY_Q_CORRECTIONS="false"
    fi
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
eSB=${ESB_OVERRIDE:-$((${nSBref} -1))}

if [[ ${bSB} -lt 0 || ${eSB} -ge ${nSBref} || ${bSB} -gt ${eSB} ]]; then
    echo "ERROR - Invalid start/end indices: bSB=${bSB}, eSB=${eSB}, tuple_count=${nSBref}"
    exit 1
fi

if [[ "${DRY_RUN_PARSE}" == "true" ]]; then
    echo "INFO - Dry-run parse mode (no fetch/processing)"
    echo "INFO - Manifest: ${MANIFEST_FILE}"
    echo "INFO - Index range: ${bSB}..${eSB}"
    for (( iSB=${bSB}; iSB<=${eSB}; iSB++ )); do
        echo "IDX=${iSB} SB_REF=${refFieldList[${iSB}]} SB_1934=${sb1934List[${iSB}]} SB_HOLO=${holoSBList[${iSB}]} SB_TARGET_1934=${calFieldList[${iSB}]} ODC_WEIGHT=${odcWeightList[${iSB}]} AMP_STRATEGY=${ampStrategyList[${iSB}]} DO_PREFLAG_REFTABLE=${doPreflagList[${iSB}]}"
    done
    exit 0
fi

if [ "${DO_FETCH_RAWDATA}" == "true" ]; then 
    for (( iSB=${bSB}; iSB<=${eSB}; iSB++ ))
    do
        ###############################################################
        sbRefNow=${refFieldList[${iSB}]}
        cd ${DIR_SB}
        if [ ! -e ${sbRefNow} ];then
            sbDir=$(ls -1d ${FETCHED_DIR}/${sbRefNow})
	    if [ "${sbDir}" != "" ] ; then
                # 1. Copy the directory from the pre-fetched area: 
                echo "INFO - Copying refField data from: ${sbDir}"
	        cp -r ${sbDir} .
	    else 
                # Perhaps, the dir has been tarred: 
                tarFile=$(ls -1d ${FETCHED_DIR}/${sbRefNow}.tar)
	        if [ "${tarFile}" != "" ] ; then
                    echo "INFO - Extracting refField data from: ${tarFile}"
	            tar xf ${tarFile} --strip-components=1
	        else 
                    echo "WARNING - Missing refField data: ${tarFile}, so looking for the .gz file."
                    tarFile=$(ls -1d ${FETCHED_DIR}/${sbRefNow}.tar.gz)
                    if [ -e "${tarFile}" ]; then 
                        echo "INFO - Extracting refField data from: ${tarFile}"
	                tar xzf ${tarFile} --strip-components=1
                    else
                        echo "ERROR: Missing refField SB ${sbRefNow}!"
                    fi
	        fi
            fi
	fi
        ###############################################################
        sbCalNow=${calFieldList[${iSB}]}
        cd ${DIR_SB}
        if [ ! -e ${sbCalNow} ];then
            sbDir=$(ls -1d ${FETCHED_DIR}/${sbCalNow})
	    if [ "${sbDir}" != "" ] ; then
                # 1. Copy the directory from the pre-fetched area: 
                echo "INFO - Copying 1934-634 cal data from: ${sbDir}"
	        cp -r ${sbDir} .
	    else 
                # Perhaps, the dir has been tarred: 
                tarFile=$(ls -1d ${FETCHED_DIR}/${sbCalNow}.tar)
	        if [ "${tarFile}" != "" ] ; then
                    echo "INFO - Extracting 1934 data from: ${tarFile}"
	            tar xf ${tarFile} --strip-components=1
	        else 
                    echo "WARNING - Missing 1934 data: ${tarFile}, so looking for the .gz file."
                    tarFile=$(ls -1d ${FETCHED_DIR}/${sbCalNow}.tar.gz)
                    if [ -e "${tarFile}" ]; then 
                        echo "INFO - Extracting 1934 data from: ${tarFile}"
	                tar xzf ${tarFile} --strip-components=1
                    else
                        echo "ERROR: Missing 1934 SB ${sbCalNow} !"
                    fi
	        fi
            fi
	fi
    done
fi
# Step-2: Begin reference field processing: 
if [ "${DO_FIND_BANDPASS}" == "true" ]; then 
    for (( iSB=${bSB}; iSB<=${eSB}; iSB++ ))
    do
        sbRefNow=${refFieldList[${iSB}]}
        sb1934Now=${sb1934List[${iSB}]}
        holoSBNow=${holoSBList[${iSB}]}
        ampStrategyNow=${ampStrategyList[${iSB}]}
        doPreflagNow=${doPreflagList[${iSB}]}
        odcWeightNow=${odcWeightList[${iSB}]}
	echo "INFO - Deriving bandpass for reference field [$iSB]: ${sbRefNow}"
        if [ -e ${DIR_SB}/${sbRefNow} ];then
            strategySuffixNow=""
            if [ "${ampStrategyNow}" != "" ]; then
                strategySuffixNow="${strategySuffixNow}_AMP_STRATEGY-${ampStrategyNow}"
            fi
            if [ "${doPreflagNow}" == "true" ]; then
                strategySuffixNow="${strategySuffixNow}-insituPreflags"
            fi

            tupleProcessingDir=${WORK_DIR}/ODC-${odcWeightNow}/SB_REF-${sbRefNow}_SB_1934-${sb1934Now}_SB_HOLO-${holoSBNow}${strategySuffixNow}
            mkdir -p ${tupleProcessingDir}
            cd ${tupleProcessingDir}

            # 
            configNow1="run_refField_SB_REF-${sbRefNow}_SB_1934-${sb1934Now}_SB_PB-${holoSBNow}.sh"

            # Load base config parameters: 
            cat "${REF_CONFIG_TEMPLATE}" >"${configNow1}"
            cat >>${configNow1} << EOF
DIR_SB=${DIR_SB}
BP_UPDATE_MODIFY_AMP_STRATEGY=${ampStrategyNow}
BPTOOL_VERSION=2.8.0-rc.1
DO_PREFLAG_REFTABLE=${doPreflagNow}
APPLY_PREFLAGS_DIRECTLY_REFTABLE=${doPreflagNow}
# Q-correction of residual X/Y gain amplitude imbalance (values passed via CLI args)
BP_UPDATE_APPLY_Q_CORRECTIONS=${APPLY_Q_CORRECTIONS}
BP_UPDATE_Q_CORR_CSV=${Q_CORR_CSV}
BP_UPDATE_Q_CORR_VARIANT=${Q_CORR_VARIANT}
BP_UPDATE_Q_CORR_ALLOW_REF_WS_MISMATCH=${Q_CORR_ALLOW_MISMATCH}
$([ -n "${Q_CORR_REF_WS}" ] && echo "BP_UPDATE_Q_CORR_REF_WS=${Q_CORR_REF_WS}" || echo "# BP_UPDATE_Q_CORR_REF_WS not set (pipeline derives from PARENT_WEIGHT_SCIENCE)")
EOF
            processASKAP.sh -r ${sbRefNow} -b ${sb1934Now} -p ${holoSBNow} -t ${configNow1}
        fi
    done
fi
