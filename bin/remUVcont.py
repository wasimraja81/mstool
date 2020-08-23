#!/usr/bin/env python 
# Import necessary modules
import sys 
import argparse 
import os
from casacore.tables import * 
#import matplotlib.pyplot as plt 
import numpy as np 
import process_bptab as pbp 
import meanrms as musigma
import finterp as fi

def parse_args():
    """
    Parse input arguments
    """
    parser = argparse.ArgumentParser(description='Remove continuum and artifacts from uv data.')

    parser.add_argument('-m','--msdata', dest='ms_data',required='true',help='Input msdata (with path)',
                        type=str)
    parser.add_argument('-np','--np', dest='poly_order', help='The polynomial order for fit',
                        default=2, type=int)
    parser.add_argument('-nh','--nh', dest='harm_order', help='The harmonic order for fit',
                        default=3, type=int)
    parser.add_argument('-npol','--npol', dest='n_pol', help='The number of polarisation in table (must be 4)',
                        default=4, type=int)
    parser.add_argument('-nwin','--nwindow', dest='n_win', help='The data will be divided in to nWin windows and fitted (moving fit)',
                        default='1', type=int)
    parser.add_argument('-f54','--fit54', dest='fit_54', help='The data will be fitted within the BeamForming interval (54xN channels). n_win will be computed internally.',
                        default='1', type=int)
    parser.add_argument('-nT','--ntaper', dest='n_Taper', help='Width in Npts of the Gaussian Taper function to remove high frequency components, especially due to flagged points',
                        default='15', type=int)
    parser.add_argument('-nI','--niter', dest='n_iter', help='Number of iterations for Fourier-interpolating across flagged points',
                        default='100', type=int)
    parser.add_argument('-r','--refant', dest='ref_ant', help='Reference Antenna',
                        default='1', type=int)
    parser.add_argument('-nl','--nleft', dest='n_left', help='Number of points to skip at the beginning of a window',
                        default='0', type=int)
    parser.add_argument('-nr','--nright', dest='n_right', help='Number of points to skip at the end of a window',
                        default='0', type=int)
    parser.add_argument('-o','--overwrite', dest='over_write', help='If True, input ms will be overwritten',
                        default=False, type=bool)



    if len(sys.argv) < 2: 
        parser.print_usage()
        sys.exit(1)

    args = parser.parse_args()
    return args


if __name__ == "__main__":
    args = parse_args()

    msData = args.ms_data

    n_p = args.poly_order 
    n_h = args.harm_order 
    n_pol = args.n_pol
    n_win = args.n_win
    fit_54 = args.fit_54
    overWrite = args.over_write
    n_right = args.n_right 
    n_left = args.n_left 

    if n_left > n_right: 
        # Use all data to fit
        n_left = 0
        n_right = 0
    if n_left < 0: 
        # Start from the first data point on the left
        n_left = 0
    if n_right < 0: 
        # Use all data for fitting:
        n_left = 0
        n_right = 0


    nTaper = args.n_Taper #15 
    nIter = args.n_iter #350

    # Main  work begins...

    # Make a copy of  the msdata for writing out UVsub data:
    if overWrite == True:
            td = table(msData, readonly=False,ack=False)
    else:
            td = table(msData, readonly=True,ack=False)
            inTabDir,inTabName = os.path.split(msData)
            print("Table path: %s" % (inTabDir))
            print("Table name: %s" % (inTabName))
            if inTabName == "":
                    index = inTabDir.index('.ms')
                    outTable = inTabDir[0:index] + ".uvsub" + ".ms"
            else:
                    index = inTabName.index('.ms')
                    outTable = inTabDir +  '/' + inTabName[0:index] + ".uvsub" + ".ms"
            print ("Copying  input  ms data to: %s \n" % (outTable))
            td.copy(outTable, deep=True, valuecopy=True, dminfo={}, endian='aipsrc', memorytable=False, copynorows=False)
            print ("Done copying...")

            ts = table(outTable, readonly=False, ack=True)

    ta = table("%s/ANTENNA"%(msData),readonly=True,ack=False)
    antNames = ta.getcol("NAME")
    nAnt = len(antNames)
    nBase = nAnt * (nAnt + 1) // 2
    f1 = td.getcol('FLAG',startrow=0,nrow=1,rowincr=1) 
    time = td.getcol('TIME',startrow=0,nrow=-1,rowincr=1)
    nChan = f1.shape[1]
    nStokes = f1.shape[2]
    nRow = time.shape[0]
    nRec = nRow // nBase

    ta.close()
    print("Input msdata: %s" % (msData))
    print("       nAnte: %d" % (nAnt))
    print("        nRec: %d" % (nRec))
    print("        nRow: %d" % (nRow))
    print("       nChan: %d" % (nChan))
    print("       nBase: %d" % (nBase))
    print("     nStokes: %d" % (nStokes))

    # If fitting to be done in beam-forming interval: 
    if (fit_54 > 0):
        #n_p = 1 
        #n_h = 2 

        nSampPerFit = 54*fit_54 #nchan # nchan
        nStagger = nSampPerFit 
        n_win = nChan//nSampPerFit
        print("The fitting will be done in 54 x",fit_54," Channel beam-forming intervals.")
    else: 
        nSampPerFit = nChan//n_win 
        nStagger= nSampPerFit//2 

    # Compute the flagging statistics of all channels in time-baseline space: 
    nBadChan_AllBaseAllTime = 0 
    bRec = 0 
    eRec = nRec
    irow = bRec*nBase

    for itime in range(bRec, eRec):
        print ("# Processing Integration Number: %5d, MJD: %f " % (itime,time[irow]/86400.0))
        #print ("#-------------------------------------------------------------- ")
        #print ("#%6s %5s %7s %5s %5s  %10s %10s  " %("Row","Rec","Base","Ant1","Ant2","nBadChan-0","nBadChan-final"))
        #print ("#-------------------------------------------------------------- ")

        # For ASKAP single beam 16k channels, 14hours observation, 
        # you will have: 
        # 16000chan * (14 x 3600s / 5s)integrations * 666 baselines = 400GB! 
        # So you will have to load the rows incrementally. 
        #f = tf.getcol('FLAG',startrow=0,nrow=-1,rowincr=1) 
        f = td.getcol('FLAG',startrow=irow,nrow=nBase,rowincr=1) 
        v = td.getcol('DATA',startrow=irow,nrow=nBase,rowincr=1) 
        # Initialise the contSub array with the original data:
        v_sub = td.getcol('DATA',startrow=irow,nrow=nBase,rowincr=1) 
        a1 = td.getcol('ANTENNA1',startrow=irow,nrow=nBase,rowincr=1) 
        a2 = td.getcol('ANTENNA2',startrow=irow,nrow=nBase,rowincr=1) 

        nBadChan_AllBase = 0 
        #++++++++++++++++++++++++++++++++++++++++++++++++++++++++
        # Find channels that stand out as outliers when all 
        # baselines are averaged for this time: 
        # 1. get the baseline-averaged spectra
        # 2. Detetct  outlier channels (could be RFI/Lines
        # 3. Update the flagArray to further exclude these points 
        #    from the fit.
        ave_x = np.zeros((nChan),dtype="complex")
        ave_y = np.zeros((nChan),dtype="complex")
        ave_ispec = np.zeros((nChan),dtype="float32")
        sumFlag_x = np.zeros((nChan),dtype="float32")
        sumFlag_y = np.zeros((nChan),dtype="float32")
        flagArr = np.ones((nChan),dtype="float32")
        for jbase in range(0,nBase):
            if a1[jbase] != a2[jbase]:
                # For xx
                flagInv =  np.array(np.logical_not(f[jbase,:,0]).astype(dtype="float32",casting='same_kind'))  
                #ave_x = np.array(ave_x + np.multiply(np.abs(v[jbase,:,0]), flagInv))
                ave_x = np.array(ave_x + np.multiply(v[jbase,:,0], flagInv))
                # Sum the flag spectra (count of good points)
                sumFlag_x = np.array(sumFlag_x + flagInv)
                #
                # Now for yy
                flagInv =  np.array(np.logical_not(f[jbase,:,3]).astype(dtype="float32",casting='same_kind'))  
                #ave_y = np.array(ave_y + np.multiply(np.abs(v[jbase,:,3]), flagInv))
                ave_y = np.array(ave_y + np.multiply(v[jbase,:,3], flagInv))
                # Sum the flag spectra (count of good points)
                sumFlag_y = np.array(sumFlag_y + flagInv)
        # Get the average spectra & avoid Inf:
        for jchan in range(0,nChan):
            if sumFlag_x[jchan] > 0 and sumFlag_y[jchan] > 0:
                ave_x[jchan] = ave_x[jchan]/sumFlag_x[jchan]
                ave_y[jchan] = ave_y[jchan]/sumFlag_y[jchan]
                flagInv[jchan] = 1.0
            else:
                ave_x[jchan] = 0.0
                ave_y[jchan] = 0.0
                flagInv[jchan] = 0.0
            ave_ispec[jchan] = np.abs(ave_x[jchan] + ave_y[jchan]) 
        # Derive outlier channels:
        ave_ispec_fit = pbp.process_bptab(inarr=ave_ispec,flagarr=flagInv,maskval=0.0,npts=nChan,nsampperfit=nSampPerFit,nstagger=nStagger,npoly=n_p,nharm=n_h,refant=0,nskipleft=n_left,nskipright=n_right) 
        resi = np.array(ave_ispec - ave_ispec_fit)
        sigma,mu = musigma.meanrms(a=resi,np=nChan)
        thresh = 1.2
        jcnt = 0
        for jchan in range(0,nChan):
            #if np.abs(resi[jchan] - mu) > thresh*sigma :
            if np.abs(resi[jchan]) > thresh*sigma :
                flagArr[jchan] = 0.0
                jcnt = jcnt  + 1
                #print ("# Excluded Channel: %6d , jchan/54: %f " % (jchan,jchan/54.0))
            else: 
                flagArr[jchan] = 1.0
        print ("# Excluded: %6d channels for Integration Number: %5d, MJD: %f " % (jcnt,itime,time[irow]/86400.0))
        print ("# sigma: %f, mu: %f " % (sigma,mu))
        #print ("# flagInv.shape: ",flagInv.shape)
        #print ("# flagArr.shape: ",flagArr.shape)
        #++++++++++++++++++++++++++++++++++++++++++++++++++++++++


        brow = itime 
        erow = brow + nBase 
    
        ibase = -1 
        ##
        for i in range(brow,erow): 
            ibase = ibase + 1 
            #if (a1[ibase] == 0) &  (a2[ibase] == 6):
            if a1[ibase] != a2[ibase]:
                #Remember flag=1 is regarded as valid Data by finterp and process_bptab. 
                # But the flag=1 in msdata means bad data. So, invert the flag Array to 
                # match the  definition in finterp & process_bptab. 
                flagMS = np.array(f[ibase,:,0].astype(dtype="float32",casting='same_kind'))   
                #flagInv =  np.array(np.logical_not(f[ibase,:,0]).astype(dtype="float32",casting='same_kind'))  
                flagInv =  np.multiply(flagArr,np.array(np.logical_not(f[ibase,:,0]).astype(dtype="float32",casting='same_kind')))
                #print ("# flagInv.shape Now: ",flagInv.shape)
                #print ("# flagArr.shape Now: ",flagArr.shape)
        
                xrtmp = np.multiply(v[ibase,:,0].real, flagInv)  
                xr = fi.finterp(inarr=xrtmp,flagarr=flagInv,maskval=0.0,npts=nChan,ntaper=nTaper,niter=nIter,refant=0)
                xr_fit = pbp.process_bptab(inarr=xr,flagarr=flagInv,maskval=0.0,npts=nChan,nsampperfit=nSampPerFit,nstagger=nStagger,npoly=n_p,nharm=n_h,refant=0,nskipleft=n_left,nskipright=n_right) 
            
      
                flagMS = np.array(f[ibase,:,0].astype(dtype="float32",casting='same_kind'))   
                #flagInv =  np.array(np.logical_not(f[ibase,:,0]).astype(dtype="float32",casting='same_kind')) 
                flagInv =  np.multiply(flagArr,np.array(np.logical_not(f[ibase,:,0]).astype(dtype="float32",casting='same_kind')))
        
                xitmp = np.multiply(v[ibase,:,0].imag, flagInv)
                xi = fi.finterp(inarr=xitmp,flagarr=flagInv,maskval=0.0,npts=nChan,ntaper=nTaper,niter=nIter,refant=0)
                xi_fit = pbp.process_bptab(inarr=xi,flagarr=flagInv,maskval=0.0,npts=nChan,nsampperfit=nSampPerFit,nstagger=nStagger,npoly=n_p,nharm=n_h,refant=0,nskipleft=n_left,nskipright=n_right) 
            
                #xr_resi = np.array(xr - xr_fit) 
                #xi_resi = np.array(xi - xi_fit)
                xr_resi = np.array(v[ibase,:,0].real - xr_fit) 
                xi_resi = np.array(v[ibase,:,0].imag - xi_fit)
            
                v_sub[ibase,:,0] = np.array(xr_resi + 1j*xi_resi) 
        
                flagMS = np.array(f[ibase,:,3].astype(dtype="float32",casting='same_kind'))   
                #flagInv =  np.array(np.logical_not(f[ibase,:,3]).astype(dtype="float32",casting='same_kind'))  
                flagInv =  np.multiply(flagArr,np.array(np.logical_not(f[ibase,:,3]).astype(dtype="float32",casting='same_kind')))
        
                yrtmp = np.multiply(v[ibase,:,3].real, flagInv)  
                yr = fi.finterp(inarr=yrtmp,flagarr=flagInv,maskval=0.0,npts=nChan,ntaper=nTaper,niter=nIter,refant=0)
                yr_fit = pbp.process_bptab(inarr=yr,flagarr=flagInv,maskval=0.0,npts=nChan,nsampperfit=nSampPerFit,nstagger=nStagger,npoly=n_p,nharm=n_h,refant=0,nskipleft=n_left,nskipright=n_right) 
            
                flagMS = np.array(f[ibase,:,3].astype(dtype="float32",casting='same_kind'))   
                #flagInv =  np.array(np.logical_not(f[ibase,:,3]).astype(dtype="float32",casting='same_kind'))  
                flagInv =  np.multiply(flagArr,np.array(np.logical_not(f[ibase,:,3]).astype(dtype="float32",casting='same_kind')))
        
                yitmp = np.multiply(v[ibase,:,3].imag, flagInv)  
                yi = fi.finterp(inarr=yitmp,flagarr=flagInv,maskval=0.0,npts=nChan,ntaper=nTaper,niter=nIter,refant=0)
                yi_fit = pbp.process_bptab(inarr=yi,flagarr=flagInv,maskval=0.0,npts=nChan,nsampperfit=nSampPerFit,nstagger=nStagger,npoly=n_p,nharm=n_h,refant=0,nskipleft=n_left,nskipright=n_right) 
            
                #v_sub[ibase,:,3] = (v[ibase,:,3].real - yr_fit) + 1j*(v[ibase,:,3].imag - yi_fit)
                #yr_resi = np.array(yr - yr_fit)
                #yi_resi = np.array(yi - yi_fit) 
                yr_resi = np.array(v[ibase,:,3].real - yr_fit) 
                yi_resi = np.array(v[ibase,:,3].imag - yi_fit)
            
                v_sub[ibase,:,3] = np.array(yr_resi + 1j*yi_resi)
            
            irow =  irow + 1 
        ##
        # Update data in new table: 
        if overWrite == True:
                td.putcol('DATA', v_sub, startrow=irow-nBase, nrow=nBase, rowincr=1)
        else:
                ts.putcol('DATA', v_sub, startrow=irow-nBase, nrow=nBase, rowincr=1)
    # Find out the total percentage of channels flagged for ALL baselines for ALL times:
    nTotVis = nChan*nBase*nRec
    if overWrite == True:
            td.flush(recursive=True)
            td.close()
    else:
            td.close()
            ts.flush(recursive=True)
            ts.close()
