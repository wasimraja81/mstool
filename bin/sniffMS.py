#!/usr/bin/env python

import sys 
import os
import argparse
import numpy as np
from casacore.tables import *
from datetime import datetime, date, time
from datetime import timedelta
from casacore.quanta import quantity 
from astropy.time import Time

"""
Code for sniffing small section data from measurement set.


                                     --wr, 20 Feb, 2020

"""

def parse_args():
    """
    Parse input arguments
    """
    parser = argparse.ArgumentParser(description='Query and print metadata information from a measurement set.')

    parser.add_argument('-m','--msdata', dest='ms_data',required='true',help='Input msdata (with path)',
                        type=str)
    parser.add_argument('-r','--recnum', dest='rec_num',help='Record Number (0-based)',
                        type=int,default=0)
    parser.add_argument('-c','--chan', dest='chan_num',help='Channel Number (0-based)',
                        type=int,default=0)
    parser.add_argument('-p','--pol', dest='pol_num',help='Polarisation Number (0-3)',
                        type=int,default=0)
    parser.add_argument('-a1','--ant1', dest='ant_num1',help=' Lower antenna number of the baseline (0-based)',
                        type=int,default=0)
    parser.add_argument('-a2','--ant2', dest='ant_num2',help='Higher antenna number of the baseline (0-based)',
                        type=int,default=1)
    parser.add_argument('-o', '--outfile', dest='out_file', help='Base name for Output files',
                        default='None',type=str)

    if len(sys.argv) < 2: 
        parser.print_usage()
        sys.exit(1)

    args = parser.parse_args()
    return args


if __name__ == "__main__":
    args = parse_args()

    msData = args.ms_data
    recNum = args.rec_num
    chanNum = args.chan_num
    polNum = args.pol_num
    antNum1 = min(args.ant_num1,args.ant_num2)
    antNum2 = max(args.ant_num1,args.ant_num2)

    outFile = args.out_file
    if (outFile == 'None'):
        path = msData.rstrip(os.sep) # Strip the slash from the right side if it was provided in the msname
        basename = os.path.basename(path)
        outFile = basename 

    outFileBaselines = outFile + ".sniff-baselines.rec-" + str(recNum) + ".chan-" + str(chanNum) + ".pol-" + str(polNum) + ".txt"
    outFileSpectra = outFile + ".sniff-spectra.rec-" + str(recNum) + ".ante-" + str(antNum1) + "-" + str(antNum2) + ".pol-" + str(polNum) + ".txt"

    fOutBaselines = open(outFileBaselines,'w')
    fOutSpectra = open(outFileSpectra,'w')


    # Open up the SPECTRAL_WINDOW table of the current ms
    tf = table("%s/SPECTRAL_WINDOW" %(msData), readonly=True,ack=False)
    nChan = tf.getcol("NUM_CHAN")   
    rFreq = tf.getcol("REF_FREQUENCY")   
    dChan = tf.getcol("CHAN_WIDTH")   
    BW = tf.getcol("EFFECTIVE_BW")   

    tf.close()
    #
    tf = table("%s/" %(msData), readonly=True,ack=False)
    beamNum = tf.getcol("FEED1")   
    tArray = tf.getcol("TIME")   
    nTime = len(tArray)
    nRows = nTime
    dArray = tf.getcol("DATA",startrow=0,nrow=1,rowincr=1)
    nPol = dArray.shape[2]
    tf.close()

    bTime = tArray[0]
    eTime = tArray[nTime-1]
    #
    tf = table("%s/ANTENNA" %(msData), readonly=True,ack=False)
    antNames = tf.getcol("NAME")   
    nAnt = len(antNames)
    nBase = nAnt * (nAnt + 1) // 2
    tf.close() 
    #
    tf = table("%s/OBSERVATION/" %(msData), readonly=True,ack=False)
    telescope = tf.getcol("TELESCOPE_NAME")   
    tf.close() 

    dT = (eTime - bTime )
    tInt = dT/nRows*nBase 
    nRec = nRows//nBase
    #
    # 
    bTime = Time(bTime/86400.0,format='mjd')
    eTime = Time(eTime/86400.0,format='mjd')

    print ("# Input msdata: %s \n" % (msData))
    print ("# %s   Observations between: %s - %s" % (telescope[0],bTime.iso,eTime.iso))
    print ("# In UTC seconds from MJD=0: %f - %f" % (bTime.mjd*86400.0,eTime.mjd*86400.0))
    print ("# ============================================")
    print ("#       Obs duration(s): ",dT)
    print ("#   Reference Frequency: ",rFreq[0])
    print ("#    Number of Channels: ",nChan[0])
    print ("#         Channel Width: ",dChan[0,0])
    print ("#       Total Bandwidth: ",BW[0,0])
    print ("#           Beam Number: ",beamNum[0])
    print ("#    Number of Antennas: ",nAnt)
    print ("#   Number of Baselines: ",nBase)
    print ("#       Number of Corrs: ",nPol)
    print ("#                 nRows: ",nRows)
    print ("#     Number of Records: ",nRec)
    print ("# Effective integration: ",tInt)
    print ("#============================================")
    print ("# Data shape (assumed) : %d x %d x %d" %(nRows,nChan[0],nPol))
    print ("# Data shape (per read): %d x %d" %(nBase,nChan[0]))

    fOutBaselines.write ("# Input msdata: %s \n" % (msData))
    fOutBaselines.write ("# %s   Observations between: %s - %s \n" % (telescope[0],bTime.iso,eTime.iso))
    fOutBaselines.write ("# In UTC seconds from MJD=0: %f - %f \n" % (bTime.mjd*86400.0,eTime.mjd*86400.0))
    fOutBaselines.write ("# ============================================ \n")
    fOutBaselines.write ("#       Obs duration(s): %f \n" %(dT))
    fOutBaselines.write ("#   Reference Frequency: %f \n" %(rFreq[0]))
    fOutBaselines.write ("#    Number of Channels: %d \n" %(nChan[0]))
    fOutBaselines.write ("#         Channel Width: %f \n" %(dChan[0,0]))
    fOutBaselines.write ("#       Total Bandwidth: %f \n" %(BW[0,0]))
    fOutBaselines.write ("#           Beam Number: %d \n" %(beamNum[0]))
    fOutBaselines.write ("#    Number of Antennas: %d \n" %(nAnt))
    fOutBaselines.write ("#   Number of Baselines: %d \n" %(nBase))
    fOutBaselines.write ("#       Number of Corrs: %d \n" %(nPol))
    fOutBaselines.write ("#                 nRows: %d \n" %(nRows))
    fOutBaselines.write ("#     Number of Records: %d \n" %(nRec))
    fOutBaselines.write ("# Effective integration: %f \n" %(tInt))
    fOutBaselines.write ("#============================================ \n")
    fOutBaselines.write ("# Data shape (assumed) : %d x %d x %d \n" %(nRows,nChan[0],nPol))
    fOutBaselines.write ("# Data shape (per read): %d x %d \n" %(nBase,nChan[0]))

    fOutSpectra.write ("# Input msdata: %s \n" % (msData))
    fOutSpectra.write ("# %s   Observations between: %s - %s \n" % (telescope[0],bTime.iso,eTime.iso))
    fOutSpectra.write ("# In UTC seconds from MJD=0: %f - %f \n" % (bTime.mjd*86400.0,eTime.mjd*86400.0))
    fOutSpectra.write ("# ============================================ \n")
    fOutSpectra.write ("#       Obs duration(s): %f \n" % (dT))
    fOutSpectra.write ("#   Reference Frequency: %f \n" % (rFreq[0]))
    fOutSpectra.write ("#    Number of Channels: %d \n" % (nChan[0]))
    fOutSpectra.write ("#         Channel Width: %f \n" % (dChan[0,0]))
    fOutSpectra.write ("#       Total Bandwidth: %f \n" % (BW[0,0]))
    fOutSpectra.write ("#           Beam Number: %d \n" % (beamNum[0]))
    fOutSpectra.write ("#    Number of Antennas: %d \n" % (nAnt))
    fOutSpectra.write ("#     Number of Spectra: %d \n" % (nBase))
    fOutSpectra.write ("#       Number of Corrs: %d \n" % (nPol))
    fOutSpectra.write ("#                 nRows: %d \n" % (nRows))
    fOutSpectra.write ("#     Number of Records: %d \n" % (nRec))
    fOutSpectra.write ("# Effective integration: %f \n" % (tInt))
    fOutSpectra.write ("#============================================ \n")
    fOutSpectra.write ("# Data shape (assumed) : %d x %d x %d \n" %(nRows,nChan[0],nPol))
    fOutSpectra.write ("# Data shape (per read): %d x %d \n" %(nBase,nChan[0]))

    # Find out the reference baseline number (assume auto-corr present, and 0-based indices
    index = 0
    for i in range(0,antNum1):
        index = index + (nAnt-i)
    refBaseNum = index + antNum2 - antNum1
    print("Baseline number for ante %d-%d : %d \n" % (antNum1,antNum2,refBaseNum))

    if recNum >= nRec or recNum < 0: 
            print ("ERROR - Specified Record Number (0-based) outside Range.")
            sys.exit(1)
    if chanNum >= nChan[0] or chanNum < 0: 
            print ("ERROR - Specified Channel Number (0-based) outside Range.")
            sys.exit(1)
    if polNum >= nPol or polNum < 0: 
            print ("ERROR - Specified Polarisation Number (0-based) outside Range.")
            sys.exit(1)
    #
    tf = table("%s/" %(msData), readonly=True,ack=False)

    bRec = recNum # recNum expected from user in 0-based counting
    eRec = recNum+1 
    iRow = bRec * nBase 
    for iRec in range(bRec,eRec):
        dArray = tf.getcol('DATA',startrow=iRow,nrow=nBase,rowincr=1)
        fArray = tf.getcol('FLAG',startrow=iRow,nrow=nBase,rowincr=1)
        a1Array = tf.getcol('ANTENNA1',startrow=iRow,nrow=nBase,rowincr=1)
        a2Array = tf.getcol('ANTENNA2',startrow=iRow,nrow=nBase,rowincr=1)
        timeNow = Time(tArray[iRow]/86400.0,format='mjd')
        fOutBaselines.write ( "# %56s" % ("++++++++++++++++++++++++++++++++++++++++++++++++++++++++ \n"))
        fOutBaselines.write ( "# NB: All indices are 0-based. \n" )
        fOutBaselines.write ( "#  \n" )
        fOutBaselines.write ( "# Visdata listed for  \n")
        fOutBaselines.write ( "#      Record Number: %d  \n" % (recNum))
        fOutBaselines.write ( "#                MJD: %f  \n" % (timeNow.mjd))
        fOutBaselines.write ( "#                UTC: %s  \n" % (timeNow.iso))
        fOutBaselines.write ( "#     Channel Number: %d  \n" % (chanNum))
        fOutBaselines.write ( "# Correlation Number: %d  \n" % (polNum))
        fOutBaselines.write ( "# %6s %4s %4s %12s %12s %10s \n" % ("Row","Ant1","Ant2","Real","Imag","Flag"))
        fOutBaselines.write ( "# %56s" % ("++++++++++++++++++++++++++++++++++++++++++++++++++++++++ \n"))
        bBase = 0
        eBase = nBase
        ibase = -1 
        # Write visibilities for all baselines given a channel & pol
        for iBase in range(0,nBase):
            re = np.real(dArray[iBase,chanNum,polNum])
            im = np.imag(dArray[iBase,chanNum,polNum])
            flagVal=fArray[iBase,chanNum,polNum]
            a1 = a1Array[iBase]
            a2 = a2Array[iBase]
            fOutBaselines.write ( "%6d %4d %4d %12.7f %12.7f %10d \n" % (iRow,a1,a2,re,im,flagVal))
            iRow = iRow + 1 
        fOutBaselines.write ( "# %6s %4s %4s %12s %12s %10s \n" % ("Row","Ant1","Ant2","Real","Imag","Flag"))
        fOutBaselines.write ( "# %56s" % ("++++++++++++++++++++++++++++++++++++++++++++++++++++++++ \n"))
        fOutBaselines.write ( "# Visdata listed for   \n")
        fOutBaselines.write ( "#      Record Number: %d  \n" % (recNum))
        fOutBaselines.write ( "#                MJD: %f  \n" % (timeNow.mjd))
        fOutBaselines.write ( "#                UTC: %s  \n" % (timeNow.iso))
        fOutBaselines.write ( "#     Channel Number: %d  \n" % (chanNum))
        fOutBaselines.write ( "# Correlation Number: %d  \n" % (polNum))
        fOutBaselines.write ( "# " )
        fOutBaselines.write ( "# NB: All indices are 0-based. \n" )
        fOutBaselines.write ( "# %56s" % ("++++++++++++++++++++++++++++++++++++++++++++++++++++++++ \n"))

        # Now write the pol-spectrum for the reference baseline for this integration:
        fOutSpectra.write ( "# %56s" % ("++++++++++++++++++++++++++++++++++++++++++++++++++++++++ \n"))
        fOutSpectra.write ( "# NB: All indices are 0-based. \n" )
        fOutSpectra.write ( "#  \n" )
        fOutSpectra.write ( "# Visdata listed for  \n")
        fOutSpectra.write ( "#      Record Number: %d  \n" % (recNum))
        fOutSpectra.write ( "#                MJD: %f  \n" % (timeNow.mjd))
        fOutSpectra.write ( "#                UTC: %s  \n" % (timeNow.iso))
        fOutSpectra.write ( "#    Baseline Number: %d  \n" % (refBaseNum))
        fOutSpectra.write ( "#          Antenna-1: %d  \n" % (antNum1))
        fOutSpectra.write ( "#          Antenna-2: %d  \n" % (antNum2))
        fOutSpectra.write ( "# Correlation Number: %d  \n" % (polNum))
        fOutSpectra.write ( "# %6s %12s %12s %10s \n" % ("Chan","Real","Imag","Flag"))
        fOutSpectra.write ( "# %56s" % ("++++++++++++++++++++++++++++++++++++++++++++++++++++++++ \n"))
        for iChan in range(0,nChan[0]):
            re = np.real(dArray[refBaseNum,iChan,polNum])
            im = np.imag(dArray[refBaseNum,iChan,polNum])
            flagVal=fArray[refBaseNum,iChan,polNum]
            fOutSpectra.write ( "%6d %12.7f %12.7f %10d \n" % (iChan,re,im,flagVal))
        
        fOutSpectra.write ( "# %6s %12s %12s %10s \n" % ("Chan","Real","Imag","Flag"))
        fOutSpectra.write ( "# %56s" % ("++++++++++++++++++++++++++++++++++++++++++++++++++++++++ \n"))
        fOutSpectra.write ( "# Visdata listed for  \n")
        fOutSpectra.write ( "#      Record Number: %d  \n" % (recNum))
        fOutSpectra.write ( "#                MJD: %f  \n" % (timeNow.mjd))
        fOutSpectra.write ( "#                UTC: %s  \n" % (timeNow.iso))
        fOutSpectra.write ( "#    Baseline Number: %d  \n" % (refBaseNum))
        fOutSpectra.write ( "#          Antenna-1: %d  \n" % (antNum1))
        fOutSpectra.write ( "#          Antenna-2: %d  \n" % (antNum2))
        fOutSpectra.write ( "# Correlation Number: %d  \n" % (polNum))
        fOutBaselines.write ( "# " )
        fOutSpectra.write ( "# NB: All indices are 0-based. \n" )
        fOutSpectra.write ( "# %56s" % ("++++++++++++++++++++++++++++++++++++++++++++++++++++++++ \n"))
    tf.close()
    fOutBaselines.close()
    fOutSpectra.close()
