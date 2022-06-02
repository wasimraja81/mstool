#!/bin/bash -l 
# =====================================================
# Example script to locate & report missing timeStamps 
# from a user-defined list of measurement sets. 
#
# The script is tuned to run on galaxy where a module 
# of the mstool software has already been built. 
#
# The script has been written keeping in mind structure 
# of the ingested ASKAP msdata. It can very easily be 
# modified for user-specific cases. 
#
# Codes used from mstool: msInfo.py 
#                  Usage: msInfo.py -h
#
# Outputs written in text files organised inside dirs 
# named after the respective SBIDs. 
#  
#                                      --wr, 25Feb2020
#
# =====================================================

# ================ User defined params =================
SBPATH="/askapbuffer/processing/askap-scheduling-blocks"
declare -a sb_list=(10612 10168)

# ===== No change should be necessary here onwards =====

nSB=${#sb_list[@]}

echo "We will process ${nSB} SBIDs..."

module unload mstool 
module load mstool 
for (( iSB=0; iSB<${nSB}; iSB++ )) 
do 
    sbid=${sb_list[$iSB]}
    SBDIR=${SBPATH}/${sbid}
    echo "Recording gaps for ALL measurement sets in SB: "${SBDIR}

    outDir="gaps_SB-${sbid}"
    mkdir -p ${outDir}
    for ms in $(ls -1d ${SBDIR}/*.ms)
    do
	#echo $ms
	beam=$(msInfo.py -m $ms -q beam)
	outFile="${outDir}/gaps.sb-${sbid}.beam-${beam}.txt"
	echo "# Recording gaps in beam-${beam} for SPW: $ms" >>${outFile}
	msInfo.py -m $ms -q findGaps >>$outFile
    done
done
module unload mstool
