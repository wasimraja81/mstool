#!/bin/bash
# TEST 2: keep amplitude strategy
# Copy of RF-midband-spectral.sh with BP_UPDATE_MODIFY_AMP_STRATEGY changed
# from "multiply" to "keep" to assess which strategy is optimal for midband.
# Note: AMP_STRATEGY in the manifest must also be set to "keep" — start_refField.slurm
# writes BP_UPDATE_MODIFY_AMP_STRATEGY from the manifest value, which overrides this template.
# All other parameters are identical to RF-midband-spectral.sh.

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

DO_STAGE_FOR_CASDA_REF=false

TABLE_BANDPASS=/askapbuffer/payne/raj030/bandpass-processing/askap-bandpass/BPCAL/calparameters.1934_bp.SB%s.tab
TABLE_LEAKAGE=/askapbuffer/payne/raj030/bandpass-processing/askap-bandpass/BPCAL/calparameters.1934_bpleakage.SB%s.tab

# 20250509 - Use the 'separate' mode instead of 'combined' to avoid issues from askapsoft/1.18.3 with changed casacore version
FILETYPE_MSSPLIT=separate
JOB_MEMORY_SPLIT_SCIENCE=32G

CHAN_RANGE_1934=7777-15552
CHAN_RANGE_SCIENCE=7777-15552

BP_UPDATE_GSM_ADAPTER_NAME="racs_global"
BP_UPDATE_FORCE_USER_DEFINED_SPECTRAL_PROPERTIES=false
MODIFY_BP_UPDATES_FROM_BPDELAYTOOL=true
BP_UPDATE_MODIFY_REFTABLE_MODE_TO_USE=beamMean #( options include: direct, beamMean)
# TEST 2: using keep instead of multiply (also set AMP_STRATEGY=keep in manifest)
BP_UPDATE_MODIFY_AMP_STRATEGY=keep #(options include: keep, replace, multiply, divide)
#BP_UPDATE_MODIFY_AMP_CHANNEL_MODE="chanMedian"
BP_UPDATE_MODIFY_AMP_CHANNEL_MODE="perChannel"
BP_UPDATE_MODIFY_PHA_STRATEGY=add #(options include: keep, replace, add, subtract)

NUM_PIXELS_REF_FIELD=8192
BP_UPDATE_MODEL_FLUX_LIMIT="0.0Jy"

DO_AVERAGE_CHANNELS=true

DO_BANDPASS_REFTABLE_SMOOTH=true
BANDPASS_REFTABLE_SMOOTH_POLY_ORDER=1
BANDPASS_REFTABLE_SMOOTH_HARM_ORDER=12
BANDPASS_REFTABLE_SMOOTH_N_WIN=1
BANDPASS_REFTABLE_SMOOTH_KEEP_ORIGINAL_FLAGS=true

#BP_UPDATE_USER_DEFINED_GSM_SPECTRAL_INDEX="-0.7"
#BP_UPDATE_USER_DEFINED_GSM_SPECTRAL_CURVATURE="0.0"
#BP_UPDATE_MODEL_FLUX_LIMIT="0.005Jy" # 5mJy seems optimal. 

BANDPASS_CAL_SOLVER=SVD
LEAKAGE_CAL_SOLVER=SVD
DO_BANDPASS_SMOOTH=true

# Alternative way to mask out small UV distances
BANDPASS_MINUV=0
UVRANGE_FLAG_1934="0~200m"
UVRANGE_FLAG_SCIENCE="0~200m"

ASKAP_MODULE_DIR=/askapbuffer/payne/raj030/askaprtModules
BPTOOL_VERSION=2.8.0
CONVOLVE_VERSION=3.0.0_ubuntu24
ASKAPSOFT_VERSION=1.23.1 #was: develop-20251117
ASKAPPY_VERSION=2.9.1
