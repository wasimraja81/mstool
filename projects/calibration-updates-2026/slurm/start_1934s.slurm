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
#module load askappipeline/axa-3741-allow-general-processing-of-1934-fields
#module load askappipeline/axa-3729-flag-bad-data-in-reference-tables


sb1934=77045     # Old 1934 
#sb1934=55539    # Old 1934 
#sb1934=61036    # Alternate 1934s
#sb1934=60862    # Alternate 1934s

holoSB_1=76554 #55219
holoSB_2=59276  # Alternate holography
PROCESS_SECOND_HOLO_SET=false

DIR_SB=/askapbuffer/payne/raj030/askap-scheduling-blocks

baseDir="/askapbuffer/payne/raj030/tickets/axa-3649-component-models/assess_1934"
baseConfig="${baseDir}/run_1934Field.sh"
workDir="/scratch/askaprt/raj030/tickets/axa-3649-component-models/assess_1934-2026"

#BP_UPDATE_MODIFY_AMP_STRATEGY="keep"
BP_UPDATE_MODIFY_AMP_STRATEGY="multiply"
if [ "${BP_UPDATE_MODIFY_AMP_STRATEGY}" != ""  ];then 
    ampStrategyString="_AMP_STRATEGY-${BP_UPDATE_MODIFY_AMP_STRATEGY}"
else
    ampStrategyString=""
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
bSB=30 #24 #19 #14 #0 #3
eSB=35 #29 #23 #18 #0 #4
#eSB=$((${nSBref} - 1))

nSB=$((${eSB} - ${bSB} + 1))

echo "INFO - We will process a total of ${nSB} 1934-638 bandpass SBIDs"
bField=0
eField=35

for (( iSB=${bSB}; iSB<=${eSB}; iSB++ ))
do
    sbRefNow=${refFieldList[${iSB}]}
    sbCalNow=${calFieldList[${iSB}]}
    odcWeightNow=${odcWeightList[${iSB}]}
    echo "INFO - Processing SB number: ${iSB} of ${nSB}"
    if [ -e ${DIR_SB}/${sbRefNow} ] && [ -e ${DIR_SB}/${sbCalNow} ];then
        dirRefProcessing1=${workDir}/ODC-${odcWeightNow}/SB_REF-${sbRefNow}_SB_1934-${sb1934}_SB_HOLO-${holoSB_1}${ampStrategyString}-insituPreflags
	dir1934Processing1="${dirRefProcessing1}/1934-processing-SB-${sbCalNow}"
	mkdir -p ${dir1934Processing1}

	# Process beam-N of field-N for the 1934 datasets: 
	# Processing for alternate holography SB-1
        echo "INFO - Processing SB_1934 ${sbCalNow} using reference field ${sbRefNow}, old 1934 ${sb1934}, SB_PB: ${holoSB_1}"
	echo "INFO - Processing dir1: ${dir1934Processing1}"
	echo " "
	for (( iField=${bField}; iField<=${eField}; iField++ ))
        do
            cd ${dir1934Processing1}
            FIELD_NOW="B1934-638_beam${iField}"
            configNow1="run_Field_${FIELD_NOW}.sh"
            mkdir -p "${FIELD_NOW}"
            cd ${FIELD_NOW}
            cat "${baseConfig}" >"${configNow1}"
            cat >> "${configNow1}" <<EOF
FIELD_SELECTION_SCIENCE="${FIELD_NOW}"
SUBMIT_JOBS=true
# We will image only beam-${iField} for field-${iField}
BEAMLIST="${iField}"
DO_CONTCUBE_IMAGING=false
DO_VALIDATION_POSSUM=false
DO_CONVOLVE_CONT=false
TABLE_BANDPASS=${dirRefProcessing1}/BPCAL/calparameters.1934_bp.SB%s.tab
TABLE_LEAKAGE=${dirRefProcessing1}/BPCAL/calparameters.1934_bpleakage.SB%s.tab
DIR_SB=${DIR_SB}
BP_UPDATE_MODIFY_AMP_STRATEGY=${BP_UPDATE_MODIFY_AMP_STRATEGY}
EOF
            processASKAP.sh -s ${sbCalNow} -b ${sbRefNow} -p ${holoSB_1} -t "${configNow1}"
        done

	if [ "${PROCESS_SECOND_HOLO_SET}" == "true" ];then
            # Processing for alternate holography SB-2
            echo "INFO - Processing SB_1934 ${sbCalNow} using reference field ${sbRefNow}, old 1934 ${sb1934}, SB_PB: ${holoSB_2}"
	    echo "INFO - Processing dir2: ${dir1934Processing2}"
	    echo " "
            dirRefProcessing2=${workDir}/ODC-${odcWeightNow}/SB_REF-${sbRefNow}_SB_1934-${sb1934}_SB_HOLO-${holoSB_2}${ampStrategyString}-insituPreflags
	    dir1934Processing2="${dirRefProcessing2}/1934-processing-SB-${sbCalNow}"
	    mkdir -p ${dir1934Processing2}
	    for (( iField=${bField}; iField<=${eField}; iField++ ))
            do
                cd ${dir1934Processing2}
                FIELD_NOW="B1934-638_beam${iField}"
                configNow2="run_Field_${FIELD_NOW}.sh"
                mkdir -p "${FIELD_NOW}"
                cd ${FIELD_NOW}
                cat "${baseConfig}" >"${configNow2}"
                cat >> "${configNow2}" <<EOF
FIELD_SELECTION_SCIENCE="${FIELD_NOW}"
SUBMIT_JOBS=true
# We will image only beam-${iField} for field-${iField}
BEAMLIST="${iField}"
DO_CONTCUBE_IMAGING=false
DO_VALIDATION_POSSUM=false
TABLE_BANDPASS=${dirRefProcessing2}/BPCAL/calparameters.1934_bp.SB%s.tab
TABLE_LEAKAGE=${dirRefProcessing2}/BPCAL/calparameters.1934_bpleakage.SB%s.tab
DIR_SB=${DIR_SB}
BP_UPDATE_MODIFY_AMP_STRATEGY=${BP_UPDATE_MODIFY_AMP_STRATEGY}
USE_CLI=true
EOF
                processASKAP.sh -s ${sbCalNow} -b ${sbRefNow} -p ${holoSB_2} -t "${configNow2}"
            done
        fi
    fi
done
