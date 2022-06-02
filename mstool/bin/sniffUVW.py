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


                                     --wr, 14 Oct, 2021

"""

def parse_args():
    """
    Parse input arguments
    """
    parser = argparse.ArgumentParser(description='Query and print UVW values for a selected baseline in a measurement set.')

    parser.add_argument('-m','--msdata', dest='ms_data',required='true',help='Input msdata (with path) [default: %(default)s]',
                        type=str)
    parser.add_argument('-c','--chan', dest='chan_num',help='Channel Number (0-based) [default: %(default)s]',
                        type=int,default=0)
    parser.add_argument('-p','--pol', dest='pol_num',help='Polarisation Number (0-3) [default: %(default)s]',
                        type=int,default=0)
    parser.add_argument('-a1','--ant1', dest='ant_num1',help=' Lower antenna number of the baseline (0-based) for which to extract spectra [default: %(default)s]',
                        type=int,default=0)
    parser.add_argument('-a2','--ant2', dest='ant_num2',help='Higher antenna number of the baseline (0-based) for which to extract spectra [default: %(default)s]',
                        type=int,default=1)
    parser.add_argument('-o', '--outfile', dest='out_file', help='Base name for Output files [default: %(default)s]',
                        default='None',type=str)
    parser.add_argument('-d', '--dryrun', help='Dry-run to query ms properties. No outputs written',
                        action='store_true')

    if len(sys.argv) < 2: 
        parser.print_usage()
        sys.exit(1)

    args = parser.parse_args()
    return args


if __name__ == "__main__":
    args = parse_args()

    msData = args.ms_data
    chanNum = args.chan_num
    polNum = args.pol_num
    antNum1 = min(args.ant_num1,args.ant_num2)
    antNum2 = max(args.ant_num1,args.ant_num2)

    outFile = args.out_file
    if (outFile == 'None'):
        path = msData.rstrip(os.sep) # Strip the slash from the right side if it was provided in the msname
        basename = os.path.basename(path)
        outFile = basename 

    outFileBaselines = outFile + ".sniff-baseline.ante-" + str(antNum1) + "-" + str(antNum2) + ".chan-" + str(chanNum) + ".pol-" + str(polNum) + ".txt"


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
    print ("#============================================")
    print ("# Output Vis (a1=%d, a2=%d, chan=%d, pol=%d) will be written to: " % (antNum1,antNum2,chanNum,polNum))
    print ("#      %s" % (outFileBaselines))
    print ("# ")
    print ("#============================================")
    if args.dryrun:
        print("This was a dry-run. Hope you found the msInfo useful. ")
        sys.exit(1)

    fOutBaselines = open(outFileBaselines,'w')

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


    #if recNum >= nRec or recNum < 0: 
    #        print ("ERROR - Specified Record Number (0-based) outside Range.")
    #        sys.exit(1)
    if chanNum >= nChan[0] or chanNum < 0: 
            print ("ERROR - Specified Channel Number (0-based) outside Range.")
            sys.exit(1)
    if polNum >= nPol or polNum < 0: 
            print ("ERROR - Specified Polarisation Number (0-based) outside Range.")
            sys.exit(1)

    # Find out the reference baseline number for which to extract the spectrum. 
    # We assume auto-corrs are present even if flagged, and 0-based indices.
    index = 0
    for i in range(0,antNum1):
        index = index + (nAnt-i)
    refBaseNum = index + antNum2 - antNum1
    print("Baseline number for ante %d-%d : %d \n" % (antNum1,antNum2,refBaseNum))
    #
    tf = table("%s/" %(msData), readonly=True,ack=False)

    #bRec = recNum # recNum expected from user in 0-based counting
    #eRec = recNum+1

    #==================================
    # To read and write ALL data, use: 
    bRec = 0 
    eRec = nRec
    #==================================
    iRow = bRec * nBase 
    fOutBaselines.write ( "# %4s %4s %4s %12s %12s %9s %9s %9s %5s %23s \n" % ("Rec","Ant1","Ant2","Real","Imag","U","V","W","Flag", "TIME (UT)"))
    for iRec in range(bRec,eRec):
        print("Processing record Number %d/%d" %(iRec,nRec))
        dArray = tf.getcol('DATA',startrow=iRow,nrow=nBase,rowincr=1)
        fArray = tf.getcol('FLAG',startrow=iRow,nrow=nBase,rowincr=1)
        a1Array = tf.getcol('ANTENNA1',startrow=iRow,nrow=nBase,rowincr=1)
        a2Array = tf.getcol('ANTENNA2',startrow=iRow,nrow=nBase,rowincr=1)
        uvwArray = tf.getcol('UVW',startrow=iRow,nrow=nBase,rowincr=1)
        timeNow = Time(tArray[iRow]/86400.0,format='mjd')
        bBase = 0
        eBase = nBase
        # Write visibilities for all baselines given a channel & pol
        #for iBase in range(0,nBase):
        re = np.real(dArray[refBaseNum,chanNum,polNum])
        im = np.imag(dArray[refBaseNum,chanNum,polNum])
        flagVal=fArray[refBaseNum,chanNum,polNum]
        a1 = a1Array[refBaseNum]
        a2 = a2Array[refBaseNum]
        u = uvwArray[refBaseNum,0]
        v = uvwArray[refBaseNum,1]
        w = uvwArray[refBaseNum,2]
        fOutBaselines.write ( "%6d %4d %4d %12.7f %12.7f %9.3f %9.3f %9.3f %5d %32s \n" % (iRec,a1,a2,re,im,u,v,w,flagVal,"# "+timeNow.iso))
        iRow = iRow + nBase #1 
    fOutBaselines.write ( "# NB: All indices are 0-based. \n" )

    tf.close()
    fOutBaselines.close()
