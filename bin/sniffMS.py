#!/usr/bin/env python

import sys 
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
    parser.add_argument('-r','--recnum', dest='rec_num',help='Record Number',
                        type=int,default=1)
    parser.add_argument('-c','--chan', dest='chan_num',help='Channel Number',
                        type=int,default=1)
    parser.add_argument('-p','--pol', dest='pol_num',help='Polarisation Number (1-4)',
                        type=int,default=1)

    if len(sys.argv) < 2: 
        parser.print_usage()
        sys.exit(1)

    args = parser.parse_args()
    return args


if __name__ == "__main__":
    args = parse_args()

    ms = args.ms_data
    recNum = args.rec_num
    chanNum = args.chan_num
    polNum = args.pol_num
    # Open up the SPECTRAL_WINDOW table of the current ms
    tf = table("%s/SPECTRAL_WINDOW" %(ms), readonly=True,ack=False)
    nChan = tf.getcol("NUM_CHAN")   
    rFreq = tf.getcol("REF_FREQUENCY")   
    dChan = tf.getcol("CHAN_WIDTH")   
    BW = tf.getcol("EFFECTIVE_BW")   

    tf.close()
    #
    tf = table("%s/" %(ms), readonly=True,ack=False)
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
    tf = table("%s/ANTENNA" %(ms), readonly=True,ack=False)
    antNames = tf.getcol("NAME")   
    nAnt = len(antNames)
    nBase = nAnt * (nAnt + 1) // 2
    tf.close() 
    #
    tf = table("%s/OBSERVATION/" %(ms), readonly=True,ack=False)
    telescope = tf.getcol("TELESCOPE_NAME")   
    tf.close() 

    dT = (eTime - bTime )
    tInt = dT/nRows*nBase 
    nRec = nRows//nBase
    #
    # 
    bTime = Time(bTime/86400.0,format='mjd')
    eTime = Time(eTime/86400.0,format='mjd')

    print ("# Input msdata: %s \n" % (ms))
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

    if recNum > nRec or recNum < 1: 
            print ("ERROR - Specified Record Number outside Range.")
            sys.exit(1)
    if chanNum > nChan[0] or chanNum < 1: 
            print ("ERROR - Specified Channel Number outside Range.")
            sys.exit(1)
    if polNum > nPol or polNum < 1: 
            print ("ERROR - Specified Polarisation Number outside Range.")
            sys.exit(1)
    #
    tf = table("%s/" %(ms), readonly=True,ack=False)

    bRec = recNum-1 # recNum expected from user in 1-based counting
    eRec = recNum 
    iRow = bRec * nBase 
    for iRec in range(bRec,eRec):
        dArray = tf.getcol('DATA',startrow=iRow,nrow=nBase,rowincr=1)
        fArray = tf.getcol('FLAG',startrow=iRow,nrow=nBase,rowincr=1)
        a1Array = tf.getcol('ANTENNA1',startrow=iRow,nrow=nBase,rowincr=1)
        a2Array = tf.getcol('ANTENNA2',startrow=iRow,nrow=nBase,rowincr=1)
        timeNow = Time(tArray[iRow]/86400.0,format='mjd')
        print ( "# %56s" % ("++++++++++++++++++++++++++++++++++++++++++++++++++++++++"))
        print ( "# NB: All indices are 1-based." )
        print ( "# " )
        print ( "# Visdata listed for ")
        print ( "#      Record Number: %d (1-based)" % (recNum))
        print ( "#                MJD: %f " % (timeNow.mjd))
        print ( "#                UTC: %s " % (timeNow.iso))
        print ( "#     Channel Number: %d (1-based)" % (chanNum))
        print ( "# Correlation Number: %d (1-based)" % (polNum))
        print ( "# %6s %4s %4s %12s %12s %10s" % ("Row","Ant1","Ant2","Real","Imag","Flag"))
        print ( "# %56s" % ("++++++++++++++++++++++++++++++++++++++++++++++++++++++++"))
        bBase = 0
        eBase = nBase
        ibase = -1 
        # Write visibilities for all baselines given a channel & pol
        for iBase in range(0,nBase):
            re = np.real(dArray[iBase,chanNum-1,polNum-1])
            im = np.imag(dArray[iBase,chanNum-1,polNum-1])
            flagVal=fArray[iBase,chanNum-1,polNum-1]
            a1 = a1Array[iBase]
            a2 = a2Array[iBase]
            print ( "%6d %4d %4d %12.7f %12.7f %10d" % (iRow,a1,a2,re,im,flagVal))
            iRow = iRow + 1 
        print ( "# %6s %4s %4s %12s %12s %10s" % ("Row","Ant1","Ant2","Real","Imag","Flag"))
        print ( "# %56s" % ("++++++++++++++++++++++++++++++++++++++++++++++++++++++++"))
        print ( "# Visdata listed for  ")
        print ( "#      Record Number: %d " % (recNum))
        print ( "#                MJD: %f " % (timeNow.mjd))
        print ( "#                UTC: %s " % (timeNow.iso))
        print ( "#     Channel Number: %d " % (chanNum))
        print ( "# Correlation Number: %d " % (polNum))
        print ( "# " )
        print ( "# NB: All indices are 1-based." )
        print ( "# %56s" % ("++++++++++++++++++++++++++++++++++++++++++++++++++++++++"))
    tf.close()
