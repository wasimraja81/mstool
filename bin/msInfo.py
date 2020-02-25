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
Code for getting metadata info from msdata.
metadata currently output include: 
	1. beamID (FeedID in casa)
	2. Frequency information
The need for this code arose when ingest 
had to write msdata split-by-beam-and-frequency. 
The ordering of the files apparently was not 
straightforward, and so the split out files 
could not be named with tags having the BeamID 
and the frequency bandID. The pipeline therefore 
needs to query metadata in the msfiles to be able 
to correctly associate the beam-frequency data. 
Issue: The "mslist" app (not regarded as part of 
ASKAPsoft, but available) is a quicklook tool 
for querying metadata. However not all fields 
can be queried using it. 
Resolution: Write a python-casacore script to 
query metadata that "mslist" can or cannot 
currently read and output. 


                                     --wr, 23 Aug, 2018

"""

def parse_args():
    """
    Parse input arguments
    """
    parser = argparse.ArgumentParser(description='Query and print metadata information from a measurement set.')

    parser.add_argument('-m','--msdata', dest='ms_data',required='true',help='Input msdata (with path)',
                        type=str)
    parser.add_argument('-q','--query', dest='query_type',required='true',choices=["beam","freq","nchan","nant","antname","listant","tobs","all","findGaps"],help='Field to query',
                        type=str)
    parser.add_argument('-f','--format', dest='out_type',choices=["detailed","simple"],help='Output format',
                        type=str,default="simple")

    if len(sys.argv) < 2: 
        parser.print_usage()
        sys.exit(1)

    args = parser.parse_args()
    return args


if __name__ == "__main__":
    args = parse_args()

    ms = args.ms_data
    query = args.query_type
    outType = args.out_type
    if outType == "detailed": 
	    detailed = True
    else: 
	    detailed = False 
    # Open up the SPECTRAL_WINDOW table of the current ms
    if query == "freq":
	    tf = table("%s/SPECTRAL_WINDOW" %(ms), readonly=True,ack=False)
	    # Read the REF_FREQUENCY information
	    rFreq = tf.getcol("REF_FREQUENCY")   
	    if detailed == True:
		    print "REFERENCE_FREQUENCY: ",rFreq[0]
	    else: 
		    print rFreq[0]
	    # Close the ms
	    tf.close()
    elif query == "nchan":
	    tf = table("%s/SPECTRAL_WINDOW" %(ms), readonly=True,ack=False)
	    # Read the REF_FREQUENCY information
	    nChan = tf.getcol("NUM_CHAN")   
	    if detailed == True: 
		    print "NUM_CHAN: ",nChan[0]
	    else: 
		    print nChan[0]
	    # Close the ms
	    tf.close()
    elif query == "nant":
	    tf = table("%s/ANTENNA" %(ms), readonly=True,ack=False)
	    # Read the ANTENNA information
	    antNames = tf.getcol("NAME")   
	    if detailed == True: 
		    print "NANT: ",nAnt
	    else: 
		    print nAnt
	    # Close the ms
	    tf.close()
    elif query == "beam":
	    # Open up the msdata
	    tf = table("%s/" %(ms), readonly=True,ack=False)
	    # Read the FEED information
	    beamNum = tf.getcol("FEED1")   
	    if detailed == True:
		    print "BEAM_ID: ",beamNum[0]
	    else: 
		    print beamNum[0]
	    # Close the ms
	    tf.close()
    elif query == "tobs":
	    # Open up the msdata
	    tf = table("%s/" %(ms), readonly=True,ack=False)
	    # Read the INTERVAL information
	    tInt = tf.getcol("INTERVAL")   
	    nSpectra = len(tInt)
	    interval = tInt[0]
	    # Close the ms
	    tf.close()
	    # Read the number of baselines: 
	    tf = table("%s/ANTENNA" %(ms), readonly=True,ack=False)
	    # Read the ANTENNA information
	    antNames = tf.getcol("NAME")   
	    nAnt = len(antNames)
	    nBase = nAnt*(nAnt+1)/2
	    # Close the ms
	    tf.close()
	    tObs = nSpectra*interval/nBase
	    if detailed == True:
		    print "TOBS: ",tObs
	    else:
		    print tObs
    elif query == "antname":
	    tf = table("%s/ANTENNA" %(ms), readonly=True,ack=False)
	    # Read the ANTENNA information
	    antNames = tf.getcol("NAME")   
	    nAnt = len(antNames)
	    if detailed == True: 
	            print("%15s" % ("#==============="))
	            print("%6s %7s" % ("#Index","Name"))
	            print("%15s" % ("#==============="))
	            for i in range(0,nAnt):
		            print("%5d %8s" % (i,antNames[i]))
	            # Close the ms
	            tf.close()
	            print("%15s" % ("#==============="))
	            print("%6s %7s" % ("#Index","Name"))
	            print("%15s" % ("#==============="))
	    else:
	            for i in range(0,nAnt):
		            print("%5d %8s" % (i,antNames[i]))
    elif query == "listant":
	    tf = table("%s/ANTENNA" %(ms), readonly=True,ack=False)
	    # Read the ANTENNA information
	    antNames = tf.getcol("NAME")   
	    antPos = tf.getcol("POSITION")   
	    nAnt = len(antNames)
	    if detailed == True: 
		    print("%65s" % ("#================================================================"))
	            print("%6s %7s %16s %16s %16s" % ("#Index","Name","X","Y","Z"))
	            print("%65s" % ("#================================================================"))
	            for i in range(0,nAnt):
		            print("%5d %8s %16.7f %16.7f %16.7f" % (i,antNames[i],antPos[i,0],antPos[i,1],antPos[i,2]))
	            # Close the ms
	            tf.close()
	            print("%65s" % ("#================================================================"))
	            print("%6s %7s %16s %16s %16s" % ("#Index","Name","X","Y","Z"))
	            print("%65s" % ("#================================================================"))
	    else:
	            for i in range(0,nAnt):
		            print("%5d %8s %16.7f %16.7f %16.7f" % (i,antNames[i],antPos[i,0],antPos[i,1],antPos[i,2]))
    elif query == "all": 
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
	    nRows = tArray.shape[0]
	    tf.close()

	    bTime = tArray[0]
	    eTime = tArray[nTime-1]
	    #
	    tf = table("%s/ANTENNA" %(ms), readonly=True,ack=False)
	    antNames = tf.getcol("NAME")   
	    nAnt = len(antNames)
	    nBase = nAnt * (nAnt + 1) / 2
	    tf.close() 
	    #
	    tf = table("%s/OBSERVATION/" %(ms), readonly=True,ack=False)
	    telescope = tf.getcol("TELESCOPE_NAME")   
	    tf.close() 

	    dT = (eTime - bTime )
	    tInt = dT/nRows*nBase 
	    nRec = nRows/nBase
	    #
	    # 
	    bTime = Time(bTime/86400.0,format='mjd')
	    eTime = Time(eTime/86400.0,format='mjd')

	    print ("%s   Observations between: %s - %s" % (telescope[0],bTime.iso,eTime.iso))
	    print ("In UTC seconds from MJD=0: %f - %f" % (bTime.mjd*86400.0,eTime.mjd*86400.0))
	    print "===================================="
	    print "      Obs duration(s): ",dT
	    print "  Reference Frequency: ",rFreq[0]
	    print "   Number of Channels: ",nChan[0]
	    print "        Channel Width: ",dChan[0,0]
	    print "      Total Bandwidth: ",BW[0,0]
	    print "          Beam Number: ",beamNum[0]
	    print "   Number of Antennas: ",nAnt
	    print "                nRows: ",nRows
	    print "    Number of Records: ",nRec
	    print "Effective integration: ",tInt
	    print "===================================="
    elif query == "findGaps": 
	    tf = table("%s/" %(ms), readonly=True,ack=False)
	    beamNum = tf.getcol("FEED1")   
	    tArray = tf.getcol("TIME")   
	    tf.close()

	    nTime = len(tArray)
	    nRows = tArray.shape[0]

	    bTime = tArray[0]
	    eTime = tArray[nTime-1]
	    #
	    tf = table("%s/ANTENNA" %(ms), readonly=True,ack=False)
	    antNames = tf.getcol("NAME")   
	    nAnt = len(antNames)
	    nBase = nAnt * (nAnt + 1) / 2
	    tf.close() 
	    #
	    dT = (eTime - bTime)
	    tInt = dT/nRows*nBase 
	    nRec = nRows/nBase

	    tol = 5.0 

            iRow = -1 
	    tRecArr = tArray[0:nRows:nBase]
	    for iRec in range(1,nRec-1):
		    tDelta = tRecArr[iRec] - tRecArr[iRec-1] 
		    if (np.abs(tDelta - tInt) > tol):
			    t1 = Time(tRecArr[iRec-1]/86400.0,format='mjd')
			    t2 = Time(tRecArr[iRec]/86400.0,format='mjd')
			    #print ("Missing sample in ms: %s between timeRange: %s and %s. RecordIds: %d - %d" % (ms,t1.mjd,t2.mjd,iRec-1,iRec))
			    print ("Missing sample in ms: %s between timeRange: %s and %s. RecordIds: %d - %d" % (ms,t1.iso,t2.iso,iRec-1,iRec))
    else: 
	    print "Invalid query parameter. See help."
