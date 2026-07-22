#!/bin/bash -l

#slurm control parameters:
SUBMIT_JOBS=true
ACCOUNT=askaprt
if [ "${CLUSTER}" == "setonix" ]; then
    PRIORITY_DEFAULT=high
fi
 
# Notifications
#EMAIL=matthew.whiting@csiro.au
#EMAIL_TYPE=FAIL
#
#data location and selection:
DIR_SB=/askapbuffer/scott/askap-scheduling-blocks
SB_1934=
 
#====================================
DO_1934_CAL=true
DO_SCIENCE_FIELD=false
DO_LEAKAGE_CAL_CONT=true

BANDPASS_CAL_SOLVER=SVD
LEAKAGE_CAL_SOLVER=SVD
# PARAMETER SETTINGS
# Channel range to use for the calibrator and science datasets
CHAN_RANGE_1934=7777-15552
# Flagging parameters
# Flag autocorrelations
FLAG_AUTOCORRELATION_1934=true

DO_BANDPASS_SMOOTH=true
BANDPASS_SMOOTH_TOOL=smooth_bandpass
BANDPASS_SMOOTH_POLY_ORDER=2
BANDPASS_SMOOTH_HARM_ORDER=0

BANDPASS_FLAG_HI_ABSORPTION=true

# Alternative way to mask out small UV distances
BANDPASS_MINUV=0
UVRANGE_FLAG_1934="0~200m"

# CASDA + Acacia storage
DO_STAGE_FOR_CASDA_1934=false
WRITE_CASDA_READY=false
TRANSITION_SB=false
BP_TO_ACACIA=false
