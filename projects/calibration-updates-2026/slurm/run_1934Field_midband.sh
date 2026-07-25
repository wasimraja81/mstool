#!/bin/bash -l
## Science-field processing template for midband (WALLABY / band-2) observations.
## Based on run_1934Field.sh; differs only in channel selection and averaging.
##
## Key midband differences vs run_1934Field.sh (lowband):
##   CHAN_RANGE_1934    = 7777-15552   (select midband channels from raw SB)
##   CHAN_RANGE_SCIENCE = 7777-15552   (select midband channels from raw SB)
##   NUM_CHAN_TO_AVERAGE = 54          (~18.5 kHz native -> ~1 MHz output channels)

#++++++++++
# TEMPLATE:
#++++++++++

JOB_TIME_DEFAULT=8:00:00
JOB_TIME_SOURCEFINDING_CONT=24:00:00
JOB_TIME_VALIDATE=24:00:00
JOB_TIME_CASDA_UPLOAD=24:00:00
ACCOUNT=askap
if [ "${CLUSTER}" == "setonix" ]; then 
    ACCOUNT=askaprt
fi

DO_PREFLAG_SCIENCE=true

DO_BANDPASS_SMOOTH=true
# Disable preflagging generation for stage-2 1934 (midband) processing.
#
# Why this is safe here:
#   In stage-1, preflags are derived from the 1934 bandpass SB (sb_1934 column
#   in the manifest) and propagated into the updated reference-field table. In
#   stage-2 we re-process the *same* 1934 SB (sb_target_1934 == sb_1934 in the
#   manifest), so no new preflagging is needed — the flags were already derived
#   from this exact data and applied upstream.
#
# Why it is needed (technical):
#   When DO_BANDPASS_SMOOTH=true, stage-1 only produces the .smooth table; the
#   plain .tab is absent. copyCalibration.sh requires the plain .tab to generate
#   preflags unless BANDPASS_CATEGORY=calibration_update, but reference-field SBs
#   with processing_category=science in their scheduling-block metadata do not
#   satisfy that condition and the pipeline errors out.
#
# WARNING: This assumption breaks if sb_target_1934 != sb_1934 (i.e. the 1934 SB
#   processed in stage-2 differs from the one used to derive the bandpass in
#   stage-1). Check the manifest before re-using this template in that scenario.
DO_GENERATE_PREFLAGS=false
DO_SPLIT_TIMEWISE=false

# 20250509 - Use the 'separate' mode instead of 'combined' to avoid issues from askapsoft/1.18.3 with changed casacore version
FILETYPE_MSSPLIT=separate

BANDPASS_CAL_SOLVER=SVD
LEAKAGE_CAL_SOLVER=SVD

DO_1934_CAL=false
DO_APPLY_LEAKAGE=true
REMOVE_LEAKAGE_OFF_AXIS_CONTCUBE=true
REMOVE_LEAKAGE_OFF_AXIS_STOKES_V=true

# ── Midband channel selection and averaging ──────────────────────────────────
CHAN_RANGE_1934=7777-15552
CHAN_RANGE_SCIENCE=7777-15552
NUM_CHAN_TO_AVERAGE=54
# ─────────────────────────────────────────────────────────────────────────────

DO_SPECTRAL_IMAGING=false
GRIDDER_WMAX=45000
CLEAN_SCALES="[0,6,15,30,45,60]"
CLEAN_PSFWIDTH=768
CLEAN_NUM_MAJORCYCLES="[5,15]"
CLEAN_MINORCYCLE_NITER="[400,3000]"

EXTERNAL_CATALOGUE="racs_low"
EMU_VALIDATION_CATALOGUES="RACS-low_config.txt,RACS-low2_config.txt"

DO_OFFSET_FIELD_IMAGING=true

SELFCAL_METHOD="CleanModel"
SELFCAL_INTERVAL="[200,60]"
CCALIBRATOR_MINUV=400

PRECONDITIONER_WIENER_ROBUSTNESS=0.0
RESTORE_PRECONDITIONER_LIST="[Wiener]"
RESTORE_PRECONDITIONER_WIENER_ROBUSTNESS=-1.0

#CONTPOL parameters
CLEAN_CONTPOL_SCALES="${CLEAN_SCALES}"

# CONTCUBE parameters
CLEAN_CONTCUBE_SCALES="${CLEAN_SCALES}"
NUM_PIXELS_CONTCUBE=5120
CLEAN_CONTCUBE_PSFWIDTH=768
CLEAN_CONTCUBE_NUM_MAJORCYCLES=10
CLEAN_CONTCUBE_MINORCYCLE_NITER=600
CLEAN_CONTCUBE_THRESHOLD_MAJORCYCLE=0.25mJy
PRECONDITIONER_CONTCUBE_WIENER_ROBUSTNESS=0.0

RESTORE_PRECONDITIONER_EXTENSION="highres"

LINMOS_CUTOFF=0.2

BMAJ_CUTOFF_CONVOLVE=15
BMAJ_CUTOFF_CONVOLVE_CONTCUBE=30

BMAJ_CONVOLVE=15
BMIN_CONVOLVE=15
BPA_CONVOLVE=0

DO_STAGE_FOR_CASDA=false
WRITE_CASDA_READY=false
ARCHIVE_SPECTRAL_MS=false
ARCHIVE_EXTRACTED_DATA=false

DO_RAPID_SURVEY=false

DO_CONTCUBE_IMAGING=true
DO_CONTPOL_IMAGING=true

CONTCUBE_POLARISATIONS="I,Q,U,V"
DO_RM_SYNTHESIS=true
DO_LEAKAGE_CAL_CONT=true

ENABLE_PA_ROTATION=true
POL_SWAP=true
