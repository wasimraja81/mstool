#!/bin/bash -l
## Summary pipeline configuration for the pipeline run on SB 76226, dated 2025-10-21-194128
#
# Template file used: /askapbuffer/payne/askapops/SST-templates/RF-lowband-averaged.sh
 
#++++++++++
# TEMPLATE:
#++++++++++

SUBMIT_JOBS=true
ACCOUNT=askaprt
if [ "${CLUSTER}" == "setonix" ]; then
    PRIORITY_DEFAULT=high
fi

#====================================
DO_1934_CAL=false
DO_SCIENCE_FIELD=false
DO_LEAKAGE_CAL_CONT=false

DO_SPLIT_TIMEWISE=false
DO_PREFLAG_SCIENCE=true


# 20250509 - Use the 'separate' mode instead of 'combined' to avoid issues from askapsoft/1.18.3 with changed casacore version
FILETYPE_MSSPLIT=separate
JOB_MEMORY_SPLIT_SCIENCE=32G

DO_AVERAGE_CHANNELS=false

DO_BANDPASS_REFTABLE_SMOOTH=true
BANDPASS_REFTABLE_SMOOTH_N_WIN=1
BANDPASS_REFTABLE_SMOOTH_POLY_ORDER=1
BANDPASS_REFTABLE_SMOOTH_HARM_ORDER=24
BANDPASS_REFTABLE_SMOOTH_KEEP_ORIGINAL_FLAGS=true

BP_UPDATE_GSM_ADAPTER_NAME=racs_global
#BP_UPDATE_GSM_REF_FREQ_HZ="887490000.0" # --> shouldn't need to be set if we use racs_low or racs_mid or racs_global

BP_UPDATE_FORCE_USER_DEFINED_SPECTRAL_PROPERTIES=true
BP_UPDATE_USER_DEFINED_GSM_SPECTRAL_INDEX="-0.7"
BP_UPDATE_USER_DEFINED_GSM_SPECTRAL_CURVATURE="0.0"
BP_UPDATE_MODEL_FLUX_LIMIT="0.005Jy" # 5mJy seems optimal. 

BANDPASS_CAL_SOLVER=SVD
LEAKAGE_CAL_SOLVER=SVD
DO_BANDPASS_SMOOTH=false

# Alternative way to mask out small UV distances
BANDPASS_MINUV=0
UVRANGE_FLAG_1934="0~200m"
UVRANGE_FLAG_SCIENCE="0~200m"

 
ASKAP_MODULE_DIR=/askapbuffer/payne/raj030/askaprtModules
BPTOOL_VERSION=2.7.2
CONVOLVE_VERSION=3.0.0_ubuntu24
ASKAPSOFT_VERSION=develop-20251117
ASKAPPY_VERSION=2.9.1 

MODIFY_BP_UPDATES_FROM_BPDELAYTOOL=true
BP_UPDATE_MODIFY_REFTABLE_MODE_TO_USE=beamMean #( options include: direct, beamMean)
BP_UPDATE_MODIFY_AMP_STRATEGY=multiply #(options include: keep, replace, multiply, divide)
BP_UPDATE_MODIFY_AMP_CHANNEL_MODE=chanMedian #(options include: chanMedian, chanMean, perChannel)
BP_UPDATE_MODIFY_PHA_STRATEGY=add #(options include: keep, replace, add, subtract)
DO_STAGE_FOR_CASDA_REF=false
#data location and selection:

TABLE_BANDPASS=/askapbuffer/payne/askapops/bandpass-processing/%s/BPCAL/calparameters.1934_bp.SB%s.tab
TABLE_LEAKAGE=/askapbuffer/payne/askapops/bandpass-processing/%s/BPCAL/calparameters.1934_bpleakage.SB%s.tab
