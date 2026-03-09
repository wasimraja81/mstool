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
for slurmEnvVar in $(env | grep SLURM_ | awk -F'=' '{print $1}'); do
    echo "Unsetting ${slurmEnvVar}..."
    unset $slurmEnvVar
done

module use /askapbuffer/payne/raj030/askaprtModules
module load askappipeline/axa-3859-fix-generate-parset-for-offset-fields
#module load askappipeline/2.23.1
#module load askappipeline/axa-3729-flag-bad-data-in-reference-tables

DO_FIND_BANDPASS=true
DO_FETCH_RAWDATA=true

SCRIPT_DIR=""
if [[ -n "${SLURM_SUBMIT_DIR:-}" ]]; then
    search_dir="${SLURM_SUBMIT_DIR}"
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
    SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
fi

echo "INFO - SCRIPT_DIR: ${SCRIPT_DIR}"
MANIFEST_FILE_DEFAULT="${SCRIPT_DIR}/../manifests/sb_manifest_reffield_average.txt"
MANIFEST_FILE="${MANIFEST_FILE:-${MANIFEST_FILE_DEFAULT}}"
BSB_OVERRIDE="${BSB_OVERRIDE:-}"
ESB_OVERRIDE="${ESB_OVERRIDE:-}"

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
mkdir -p ${DIR_SB}

WORK_DIR="/scratch/askaprt/raj030/tickets/axa-3649-component-models/assess_1934-2026"
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
    local default_amp="${BP_UPDATE_MODIFY_AMP_STRATEGY}"
    local default_do_preflag="${DO_PREFLAG_REFTABLE}"
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
                ODC_WEIGHT_ID|ODC|WEIGHT_ID)
                    default_odc="$(strip_numeric_tag "${cfg_val}" "ODC-")"
                    ;;
                AMP_STRATEGY)
                    default_amp="${cfg_val}"
                    ;;
                DO_PREFLAG_REFTABLE|PREFLAGGING_STRATEGY|PREFLAG_STRATEGY|FLAG_STRATEGY)
                    local normalized_do_preflag
                    normalized_do_preflag="$(normalize_do_preflag_value "${cfg_val}")"
                    if [[ -z "${normalized_do_preflag}" ]]; then
                        echo "WARNING: Invalid DO_PREFLAG_REFTABLE value '${cfg_val}' on line ${line_no}; expected true/false or insituPreflags/none"
                    else
                        default_do_preflag="${normalized_do_preflag}"
                    fi
                    ;;
            esac
            continue
        fi

        line="${line//,/ }"
        local col1="" col2="" col3="" col4="" col5="" col6="" col7="" extra=""
        read -r col1 col2 col3 col4 col5 col6 col7 extra <<< "${line}"

        # Optional leading row index:
        # idx sb_ref sb_1934 sb_holo sb_target_1934 [odc_weight_id] [amp_strategy] [do_preflag_reftable]
        if [[ "${col1}" =~ ^[0-9]+$ ]]; then
            col1="${col2}"
            col2="${col3}"
            col3="${col4}"
            col4="${col5}"
            col5="${col6}"
            col6="${col7}"
            col7="${extra}"
            extra=""
        fi

        local col1_lc
        col1_lc="$(echo "${col1}" | tr '[:upper:]' '[:lower:]')"
        if [[ "${col1_lc}" == "sb_ref" || "${col1_lc}" == "sbref" ]]; then
            continue
        fi

        if [[ -z "${col1}" || -z "${col2}" || -z "${col3}" || -z "${col4}" ]]; then
            echo "WARNING: Skipping manifest line ${line_no} (expected 4-8 columns: [idx] sb_ref sb_1934 sb_holo sb_target_1934 [odc_weight_id] [amp_strategy] [do_preflag_reftable])"
            continue
        fi
        if [[ -n "${extra}" ]]; then
            echo "WARNING: Skipping manifest line ${line_no} (too many columns)"
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
        local token
        for token in "${col5}" "${col6}" "${col7}"; do
            [[ -z "${token}" ]] && continue
            if [[ "${token}" =~ ^(ODC-)?[0-9]+$ ]]; then
                row_odc="$(strip_numeric_tag "${token}" "ODC-")"
            elif [[ "${token}" =~ [Pp]reflag || "${token}" =~ ^(none|off|on|true|false|yes|no|1|0)$ ]]; then
                local normalized_row_do_preflag
                normalized_row_do_preflag="$(normalize_do_preflag_value "${token}")"
                if [[ -z "${normalized_row_do_preflag}" ]]; then
                    echo "WARNING: Skipping manifest line ${line_no} (invalid do_preflag token '${token}')"
                    continue 2
                fi
                row_do_preflag="${normalized_row_do_preflag}"
            else
                row_amp="${token}"
            fi
        done

        if [[ -z "${row_odc}" ]]; then
            echo "WARNING: Skipping manifest line ${line_no} (missing ODC weight ID)"
            continue
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
else
    echo "WARNING - Manifest not found (${MANIFEST_FILE}); falling back to built-in tuple lists"
    for (( i=0; i<${#refFieldList[@]}; i++ )); do
        sb1934List+=("${DEFAULT_SB1934}")
        holoSBList+=("${DEFAULT_HOLOSB}")
        ampStrategyList+=("${BP_UPDATE_MODIFY_AMP_STRATEGY}")
        doPreflagList+=("${DO_PREFLAG_REFTABLE}")
    done
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
            if [ "${doPreflagNow}" == "true" ] && [ "${ampStrategyNow}" != "" ]; then
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
EOF
            processASKAP.sh -r ${sbRefNow} -b ${sb1934Now} -p ${holoSBNow} -t ${configNow1}
        fi
    done
fi
