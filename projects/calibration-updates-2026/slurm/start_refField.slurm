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
#module load askappipeline/axa-3729-flag-bad-data-in-reference-tables

DO_FIND_BANDPASS=true
DO_FETCH_RAWDATA=true
PROCESS_SECOND_HOLO_SET=false

BP_UPDATE_MODIFY_AMP_STRATEGY=multiply
#BP_UPDATE_MODIFY_AMP_STRATEGY=""
if [ "${BP_UPDATE_MODIFY_AMP_STRATEGY}" != ""  ];then 
    ampStrategyString="_AMP_STRATEGY-${BP_UPDATE_MODIFY_AMP_STRATEGY}"
else
    ampStrategyString=""
fi

sb1934=77045     # Old 1934
#sb1934=55539    # Old 1934 
#sb1934=61036    # Alternate 1934s
#sb1934=60862    # Alternate 1934s

holoSB_1=76554 #55219
holoSB_2=59276  # Alternate holography
DIR_SB=/askapbuffer/payne/raj030/askap-scheduling-blocks
mkdir -p ${DIR_SB}

dataDir="/askapbuffer/payne/raj030/tickets/axa-3649-component-models/assess_1934"
workDir="/scratch/askaprt/raj030/tickets/axa-3649-component-models/assess_1934-2026"
fetchedDir="/askapbuffer/payne/dmitchell/askap-scheduling-blocks"
#fetchedDir="/scratch/askaprt/tgalvin/racs_low3"
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
bSB=30 #24 #19 #14 #6
eSB=35 #29 #23 # 18 #7 #$((${nSBref} -1 ))

if [ "${DO_FETCH_RAWDATA}" == "true" ]; then 
    for (( iSB=${bSB}; iSB<=${eSB}; iSB++ ))
    do
        ###############################################################
        sbRefNow=${refFieldList[${iSB}]}
        cd ${DIR_SB}
        if [ ! -e ${sbRefNow} ];then
            sbDir=$(ls -1d ${fetchedDir}/${sbRefNow})
	    if [ "${sbDir}" != "" ] ; then
                # 1. Copy the directory from the pre-fetched area: 
                echo "INFO - Copying refField data from: ${sbDir}"
	        cp -r ${sbDir} .
	    else 
                # Perhaps, the dir has been tarred: 
                tarFile=$(ls -1d ${fetchedDir}/${sbRefNow}.tar)
	        if [ "${tarFile}" != "" ] ; then
                    echo "INFO - Extracting refField data from: ${tarFile}"
	            tar xf ${tarFile} --strip-components=1
	        else 
                    echo "WARNING - Missing refField data: ${tarFile}, so looking for the .gz file."
                    tarFile=$(ls -1d ${fetchedDir}/${sbRefNow}.tar.gz)
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
            sbDir=$(ls -1d ${fetchedDir}/${sbCalNow})
	    if [ "${sbDir}" != "" ] ; then
                # 1. Copy the directory from the pre-fetched area: 
                echo "INFO - Copying 1934-634 cal data from: ${sbDir}"
	        cp -r ${sbDir} .
	    else 
                # Perhaps, the dir has been tarred: 
                tarFile=$(ls -1d ${fetchedDir}/${sbCalNow}.tar)
	        if [ "${tarFile}" != "" ] ; then
                    echo "INFO - Extracting 1934 data from: ${tarFile}"
	            tar xf ${tarFile} --strip-components=1
	        else 
                    echo "WARNING - Missing 1934 data: ${tarFile}, so looking for the .gz file."
                    tarFile=$(ls -1d ${fetchedDir}/${sbCalNow}.tar.gz)
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
        odcWeightNow=${odcWeightList[${iSB}]}
	echo "INFO - Deriving bandpass for reference field [$iSB]: ${sbRefNow}"
        if [ -e ${DIR_SB}/${sbRefNow} ];then
            dirNow1=${workDir}/ODC-${odcWeightNow}/SB_REF-${sbRefNow}_SB_1934-${sb1934}_SB_HOLO-${holoSB_1}${ampStrategyString}-insituPreflags
            mkdir -p ${dirNow1}
            cd ${dirNow1}

            # 
            configNow1="run_refField_SB_REF-${sbRefNow}_SB_1934-${sb1934}_SB_PB-${holoSB_1}.sh"

            # Load base config parameters: 
            cat ${dataDir}/run_refField.sh >${configNow1}
            cat >>${configNow1} << EOF
DIR_SB=${DIR_SB}
BP_UPDATE_MODIFY_AMP_STRATEGY=${BP_UPDATE_MODIFY_AMP_STRATEGY}
BPTOOL_VERSION=2.8.0-rc.1
DO_PREFLAG_REFTABLE=true
APPLY_PREFLAGS_DIRECTLY_REFTABLE=true
EOF
            processASKAP.sh -r ${sbRefNow} -b ${sb1934} -p ${holoSB_1} -t ${configNow1}

	    if [ "${PROCESS_SECOND_HOLO_SET}" == "true" ];then
                dirNow2=${workDir}/ODC-${odcWeightNow}/SB_REF-${sbRefNow}_SB_1934-${sb1934}_SB_HOLO-${holoSB_2}${ampStrategyString}-insituPreflags
                mkdir -p ${dirNow2}
                cd ${dirNow2}
                configNow2="run_refField_SB_REF-${sbRefNow}_SB_1934-${sb1934}_SB_PB-${holoSB_2}.sh"

                # Load base config parameters: 
                cat ${dataDir}/run_refField.sh >${configNow2}
                cat >>${configNow2} << EOF
DIR_SB=${DIR_SB}
BP_UPDATE_MODIFY_AMP_STRATEGY=${BP_UPDATE_MODIFY_AMP_STRATEGY}
BPTOOL_VERSION=2.8.0-rc.1
DO_PREFLAG_REFTABLE=true
APPLY_PREFLAGS_DIRECTLY_REFTABLE=true
EOF
                processASKAP.sh -r ${sbRefNow} -b ${sb1934} -p ${holoSB_2} -t ${configNow2}
            fi
        fi
    done
fi
