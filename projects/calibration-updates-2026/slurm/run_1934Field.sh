#!/bin/bash -l
## Summary pipeline configuration for the pipeline run on SB 76230, dated 2025-10-29-055053
#
# Template file used: /askapbuffer/payne/askapops/SST-templates/EMU-POSSUM-merged-band1.sh
# User configuration used: run_emuField.sh
 
#++++++++++
# TEMPLATE:
#++++++++++
#Parset received from Josh Marvil for processing EMU+POSSUM full survey fields:
  
JOB_TIME_DEFAULT=8:00:00
JOB_TIME_SOURCEFINDING_CONT=24:00:00
JOB_TIME_VALIDATE=24:00:00
JOB_TIME_CASDA_UPLOAD=24:00:00
#EMAIL=Matthew.Whiting@csiro.au
#EMAIL_TYPE=FAIL
ACCOUNT=askap
if [ "${CLUSTER}" == "setonix" ]; then 
    ACCOUNT=askaprt
fi

DO_PREFLAG_SCIENCE=true

DO_BANDPASS_SMOOTH=false
DO_SPLIT_TIMEWISE=false
 
# 20250509 - Use the 'separate' mode instead of 'combined' to avoid issues from askapsoft/1.18.3 with changed casacore version
FILETYPE_MSSPLIT=separate

BANDPASS_CAL_SOLVER=SVD
LEAKAGE_CAL_SOLVER=SVD

DO_1934_CAL=false
DO_APPLY_LEAKAGE=true
REMOVE_LEAKAGE_OFF_AXIS_CONTCUBE=true

# 24/4/24 - changing this to true following request from Jennifer West
REMOVE_LEAKAGE_OFF_AXIS_STOKES_V=true

NUM_CHAN_TO_AVERAGE=1
DO_SPECTRAL_IMAGING=false
# 20240729 - Use default nwplanes
#GRIDDER_NWPLANES=557
GRIDDER_WMAX=45000
CLEAN_SCALES="[0,6,15,30,45,60]"
CLEAN_PSFWIDTH=768
CLEAN_NUM_MAJORCYCLES="[5,15]"
# 20240729 - Use default n-sigma threshold
#CLEAN_THRESHOLD_MINORCYCLE="[30%, 0.25mJy, 0.03mJy]"
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
CLEAN_CONTPOL_SCALES="${CLEAN_SCALES}" # Be mindful of the format if CLEAN_SCALES varies with selfcal loops.
 
# CONTCUBE parameters
CLEAN_CONTCUBE_SCALES="${CLEAN_SCALES}" # Be mindful of the format if CLEAN_SCALES varies with selfcal loops.
NUM_PIXELS_CONTCUBE=5120
CLEAN_CONTCUBE_PSFWIDTH=768
CLEAN_CONTCUBE_NUM_MAJORCYCLES=10
CLEAN_CONTCUBE_MINORCYCLE_NITER=600
CLEAN_CONTCUBE_THRESHOLD_MAJORCYCLE=0.25mJy
PRECONDITIONER_CONTCUBE_WIENER_ROBUSTNESS=0.0

RESTORE_PRECONDITIONER_EXTENSION="highres"

LINMOS_CUTOFF=0.2

#ASKAP_PB_TT_IMAGE="To be provided by OPS-processing team..."
#ASKAP_PB_CUBE_IMAGE="To be provided by OPS-processing team..."

BMAJ_CUTOFF_CONVOLVE=15
BMAJ_CUTOFF_CONVOLVE_CONTCUBE=30

BMAJ_CONVOLVE=15
BMIN_CONVOLVE=15
BPA_CONVOLVE=0
  
DO_STAGE_FOR_CASDA=true
## # stage them onto askapbuffer prior to casda ingest
## COPY_TO_BUFFER=true
### Temporary fix while CASDA is offline, to prevent flooding when it comes back
## CASDA_UPLOAD_DIR=/askapbuffer/payne/askapops/science-processing/FOR-CASDA
###
WRITE_CASDA_READY=true
ARCHIVE_SPECTRAL_MS=false
ARCHIVE_EXTRACTED_DATA=false
  
PROJECT_ID=AS201
CONTINUUM_PROJECT_ID=AS201
POLARISATION_PROJECT_ID=AS203

OBS_PROGRAM="EMU Survey"


# ADDED By Wasim & Matt:
# Will produce Stokes I continuum cubes and Stokes V MFS image in addition to the Stokes I MFS from the selfcal
DO_CONTCUBE_IMAGING=true
DO_CONTPOL_IMAGING=true


CONTCUBE_POLARISATIONS="I,Q,U,V"
DO_RM_SYNTHESIS=true
DO_LEAKAGE_CAL_CONT=true

ENABLE_PA_ROTATION=true
POL_SWAP=true

WRITETYPE_LINMOS_CONTCUBE="parallel"

SELAVY_WEIGHTS_CUTOFF=0.25 
#CPUS_PER_CORE_SELAVY=2 

# RM-synthesis 
SELAVY_POL_DELTA_PHI=10
SELAVY_POL_NUM_PHI_CHAN=300

CUBES_ON_SINGLE_OST=true
DO_VALIDATION_POSSUM=true

# To facilitate off-axis calibration, record component spectra per beam:
DO_SOURCE_FINDING_BEAMWISE=true
# Store the beamwise spectra in FITS tables
USE_FITS_TABLE_FOR_EXTRACTED_SPECTRA_BEAMWISE=true
# and remove the individual spectra once tarred up
PURGE_SPECTRA_AFTER_TAR=true

# Turn on fast-imaging and transient detection
DO_TRANSIENT_IMAGING=false
TRANSIENT_OUTPUT_DESTINATION=/scratch/ja3/vaster
JOB_MEMORY_TRANSIENT_CONTSUB=128G
TRANSIENT_CONTSUB_NTASKS=32
TRANSIENT_CONTSUB_NPPN=32
USE_PARALLEL_WRITE_MS=true


#######
# New parameters for processing on setonix
if [ "${CLUSTER}" == "setonix" ]; then 

    CORES_PER_NODE_CONTCUBE_IMAGING=33
    NCHAN_PER_CORE_CONTCUBE=9
    NUM_CORES_CONTCUBE_LINMOS=144
    CORES_PER_NODE_CONTCUBE_LINMOS=24

    # Test fast creation
    CONTCUBE_ALLOCATION_TYPE=fast

    # set memory
    JOB_MEMORY_SPLIT_SCIENCE=8G
    JOB_MEMORY_APPLY_BANDPASS=8G

    JOB_MEMORY_CONVOLVE=60G
    
fi


 
#+++++++++++++
# USER CONFIG:
#+++++++++++++
# From the command line (-s):
SB_SCIENCE=74691
# From the command line (-b):
SB_1934=74689
# From the command line (-p):
SB_PB=73441

TABLE_BANDPASS=/scratch/askaprt/raj030/tickets/axa-3649-component-models/EMU-POSSUM/74689_ref_flagging-3/BPCAL/calparameters.1934_bp.SB%s.tab
TABLE_LEAKAGE=/scratch/askaprt/raj030/tickets/axa-3649-component-models/EMU-POSSUM/74689_ref_flagging-3/BPCAL/calparameters.1934_bpleakage.SB%s.tab
CASDA_UPLOAD_DIR=For-Casda
TRANSITION_SB=false

ASKAP_MODULE_DIR=/askapbuffer/payne/raj030/askaprtModules

BPTOOL_VERSION=2.8.0-rc.1 #2.7.2
CONVOLVE_VERSION=3.0.0_ubuntu24
ASKAPSOFT_VERSION=1.21.2 #develop-20251117
ASKAPPY_VERSION=2.9.1 

DO_CONT_IMAGING=true
DO_CONTCUBE_IMAGING=false
DO_CONTPOL_IMAGING=false

BMAJ_CUTOFF_CONVOLVE=""
BMAJ_CUTOFF_CONVOLVE_CONTCUBE=""

BMAJ_CONVOLVE=""
BMIN_CONVOLVE=""
BPA_CONVOLVE=0

PURGE_INTERIM_MS_SCI=false
DO_RAPID_SURVEY=false
USE_CLI=true
