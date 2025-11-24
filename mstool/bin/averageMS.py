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
import shutil
import matplotlib.pyplot as plt
import matplotlib as mpl

"""
Code for vector averaging measurement set data with options to output
Stokes parameters (I, Q, U, V) or retain linear correlations (XX, XY, YX, YY).

Vector averaging preserves phase information by averaging complex visibilities.

Stokes parameter definitions:
    I = XX + YY
    Q = XX - YY
    U = XY + YX
    V = XY - YX

                                     --wr, 24 Nov, 2025

"""

def parse_args():
    """
    Parse input arguments
    """
    parser = argparse.ArgumentParser(description='Vector average a measurement set with polarization options.')

    parser.add_argument('-i','--input', dest='input_ms',required=True,
                        help='Input measurement set (with path)',
                        type=str)
    parser.add_argument('-o','--output', dest='output_file',required=False,
                        help='Output text file (with path). Default: auto-generated from input MS name and parameters',
                        type=str, default=None)
    parser.add_argument('-t','--tavg', dest='time_avg',
                        help='Number of time integrations to average. Use -1 or 0 to average ALL integrations [default: %(default)s]',
                        type=int,default=1)
    parser.add_argument('-f','--favg', dest='freq_avg',
                        help='Number of frequency channels to average. Use -1 or 0 to average ALL channels [default: %(default)s]',
                        type=int,default=1)
    parser.add_argument('-p','--pol-mode', dest='pol_mode',
                        help='Polarization mode: "linear" (XX,XY,YX,YY) or "stokes" (I,Q,U,V) [default: %(default)s]',
                        type=str,default='linear',choices=['linear','stokes'])
    parser.add_argument('-d', '--dryrun', help='Dry-run to check parameters. No outputs written',
                        action='store_true')
    parser.add_argument('-a1','--ant1', dest='ant_num1',
                        help='Lower antenna number of the baseline (0-based) for spectrum extraction. Use -1 to average all baselines [default: %(default)s]',
                        type=int,default=0)
    parser.add_argument('-a2','--ant2', dest='ant_num2',
                        help='Higher antenna number of the baseline (0-based) for spectrum extraction. Use -1 to average all baselines [default: %(default)s]',
                        type=int,default=1)
    parser.add_argument('--plot-output', dest='plot_file',
                        help='Output plot filename base (default: auto-generated from output filename)',
                        type=str,default=None)
    parser.add_argument('--show-plot', dest='show_plot',
                        help='Display plot interactively (in addition to saving)',
                        action='store_true')
    parser.add_argument('--ylim-pol', dest='ylim_pol', nargs=2, type=float,
                        help='Y-axis limits for polarization degree plots as [ymin ymax] in percent. Default: auto-scale based on data',
                        default=None)

    if len(sys.argv) < 2: 
        parser.print_usage()
        sys.exit(1)

    args = parser.parse_args()
    return args


def linear_to_stokes(vis_data):
    """
    Convert linear polarization correlations to Stokes parameters.
    
    Input: vis_data with shape [..., nPol] where nPol=4 (XX, XY, YX, YY)
    Output: stokes_data with shape [..., 4] (I, Q, U, V)
    
    Definitions:
        I = XX + YY
        Q = XX - YY
        U = XY + YX
        V = XY - YX
    """
    if vis_data.shape[-1] != 4:
        raise ValueError(f"Expected 4 polarizations for Stokes conversion, got {vis_data.shape[-1]}")
    
    XX = vis_data[..., 0]
    XY = vis_data[..., 1]
    YX = vis_data[..., 2]
    YY = vis_data[..., 3]
    
    I = XX + YY
    Q = XX - YY
    U = XY + YX
    V = XY - YX
    
    stokes_data = np.stack([I, Q, U, V], axis=-1)
    return stokes_data


def average_data(data, flags, time_avg, freq_avg):
    """
    Vector average complex visibility data.
    
    Args:
        data: Complex array of shape [nTime, nChan, nPol]
        flags: Boolean array of same shape
        time_avg: Number of time samples to average
        freq_avg: Number of frequency channels to average
    
    Returns:
        avg_data: Averaged complex data of shape [nChanOut, nPol]
        avg_flags: Averaged flags (True if all input samples flagged)
    """
    nTime, nChan, nPol = data.shape
    
    # Calculate output dimensions
    nTimeOut = nTime // time_avg
    nChanOut = nChan // freq_avg
    
    # Trim data to fit exact averaging bins
    nTimeUse = nTimeOut * time_avg
    nChanUse = nChanOut * freq_avg
    
    data_trim = data[:nTimeUse, :nChanUse, :]
    flags_trim = flags[:nTimeUse, :nChanUse, :]
    
    # Reshape for averaging
    # [nTimeOut, time_avg, nChanOut, freq_avg, nPol]
    data_reshaped = data_trim.reshape(nTimeOut, time_avg, nChanOut, freq_avg, nPol)
    flags_reshaped = flags_trim.reshape(nTimeOut, time_avg, nChanOut, freq_avg, nPol)
    
    # Create mask (True for good data, False for flagged)
    mask = ~flags_reshaped
    
    # Perform weighted average (unflagged data only)
    # Use np.ma for masked array operations
    masked_data = np.ma.array(data_reshaped, mask=~mask)
    avg_data = np.ma.mean(masked_data, axis=(1, 3)).filled(0)
    
    # Flag output if all input samples were flagged
    avg_flags = np.all(flags_reshaped, axis=(1, 3))
    
    # Squeeze out singleton time dimension if present (nTimeOut == 1)
    avg_data = np.squeeze(avg_data)
    avg_flags = np.squeeze(avg_flags)
    
    # Ensure we always return at least 2D arrays [nChan, nPol]
    if avg_data.ndim == 1:
        avg_data = avg_data.reshape(1, -1)
        avg_flags = avg_flags.reshape(1, -1)
    
    return avg_data, avg_flags


def get_ms_info(ms_path):
    """
    Extract metadata from measurement set.
    """
    info = {}
    
    # SPECTRAL_WINDOW table
    tf = table(f"{ms_path}/SPECTRAL_WINDOW", readonly=True, ack=False)
    info['nChan'] = tf.getcol("NUM_CHAN")[0]
    info['refFreq'] = tf.getcol("REF_FREQUENCY")[0]
    info['chanWidth'] = tf.getcol("CHAN_WIDTH")[0]
    info['totalBW'] = tf.getcol("EFFECTIVE_BW")[0]
    tf.close()
    
    # Main table
    tf = table(f"{ms_path}/", readonly=True, ack=False)
    info['timeArray'] = tf.getcol("TIME")
    info['nRows'] = len(info['timeArray'])
    info['beamNum'] = tf.getcol("FEED1")[0]  # Get beam number
    
    # Get data shape from first row
    sample_data = tf.getcol("DATA", startrow=0, nrow=1, rowincr=1)
    info['nPol'] = sample_data.shape[2]
    tf.close()
    
    # ANTENNA table
    tf = table(f"{ms_path}/ANTENNA", readonly=True, ack=False)
    info['antNames'] = tf.getcol("NAME")
    info['nAnt'] = len(info['antNames'])
    info['nBase'] = info['nAnt'] * (info['nAnt'] + 1) // 2
    tf.close()
    
    # OBSERVATION table
    tf = table(f"{ms_path}/OBSERVATION/", readonly=True, ack=False)
    info['telescope'] = tf.getcol("TELESCOPE_NAME")[0]
    tf.close()
    
    # Calculate records
    info['nRec'] = info['nRows'] // info['nBase']
    
    return info


if __name__ == "__main__":
    args = parse_args()

    inputMS = args.input_ms
    outputFile = args.output_file
    timeAvg = args.time_avg
    freqAvg = args.freq_avg
    polMode = args.pol_mode
    antNum1 = args.ant_num1
    antNum2 = args.ant_num2
    
    # Check if averaging all baselines
    averageAllBaselines = (antNum1 == -1 or antNum2 == -1)
    if averageAllBaselines:
        antNum1 = -1
        antNum2 = -1
    else:
        antNum1 = min(antNum1, antNum2)
        antNum2 = max(antNum1, antNum2)
    
    # Check input MS exists
    if not os.path.exists(inputMS):
        print(f"ERROR: Input MS does not exist: {inputMS}")
        sys.exit(1)
    
    # Generate default output filename if not provided
    if outputFile is None:
        # Extract MS basename
        msPath = inputMS.rstrip(os.sep)
        msBasename = os.path.basename(msPath)
        # Remove .ms extension if present
        if msBasename.endswith('.ms'):
            msBasename = msBasename[:-3]
        
        # Build descriptive filename
        if averageAllBaselines:
            baseStr = "allcross"
        else:
            baseStr = f"base{antNum1}-{antNum2}"
        
        tavgStr = f"tavg{timeAvg}" if timeAvg > 0 else "tavgAll"
        favgStr = f"favg{freqAvg}" if freqAvg > 0 else "favgAll"
        
        outputFile = f"{msBasename}.{baseStr}.{tavgStr}.{favgStr}.{polMode}.txt"
        print(f"Auto-generated output filename: {outputFile}")
    
    # Get MS information
    print("Reading input MS metadata...")
    msInfo = get_ms_info(inputMS)
    
    nChan = msInfo['nChan']
    nPol = msInfo['nPol']
    nRec = msInfo['nRec']
    nBase = msInfo['nBase']
    nRows = msInfo['nRows']
    
    # Handle "average all" option for time
    if timeAvg <= 0:
        timeAvg = nRec
        print(f"Time averaging set to ALL integrations: {timeAvg}")
    
    # Handle "average all" option for frequency
    if freqAvg <= 0:
        freqAvg = nChan
        print(f"Frequency averaging set to ALL channels: {freqAvg}")
    
    # Calculate output dimensions
    nRecOut = nRec // timeAvg
    nChanOut = nChan // freqAvg
    nRowsOut = nRecOut * nBase
    
    # Validate polarization mode
    if polMode == 'stokes' and nPol != 4:
        print(f"ERROR: Stokes conversion requires 4 polarizations, found {nPol}")
        sys.exit(1)
    
    # Validate antenna numbers and calculate baseline
    if averageAllBaselines:
        refBaseNum = -1
        baselineLabel = "ALL"
    else:
        if antNum1 >= msInfo['nAnt'] or antNum2 >= msInfo['nAnt']:
            print(f"ERROR: Antenna numbers must be < {msInfo['nAnt']}")
            sys.exit(1)
        
        # Calculate baseline number
        index = 0
        for i in range(0, antNum1):
            index = index + (msInfo['nAnt'] - i)
        refBaseNum = index + antNum2 - antNum1
        baselineLabel = f"{antNum1}-{antNum2} (baseline #{refBaseNum})"
    
    print("\n" + "="*60)
    print("MEASUREMENT SET SPECTRUM EXTRACTION")
    print("="*60)
    print(f"Input MS:           {inputMS}")
    print(f"Output file:        {outputFile}")
    print(f"Telescope:          {msInfo['telescope']}")
    print(f"Number of Antennas: {msInfo['nAnt']}")
    print(f"Number of Baselines: {nBase}")
    print(f"Selected Baseline:  {baselineLabel}")
    print("-"*60)
    print(f"Input  - Records:   {nRec}")
    print(f"Input  - Channels:  {nChan}")
    print(f"Input  - Pols:      {nPol}")
    print(f"Input  - Rows:      {nRows}")
    print("-"*60)
    print(f"Time averaging:     {timeAvg} integrations")
    print(f"Freq averaging:     {freqAvg} channels")
    print(f"Polarization mode:  {polMode}")
    print("-"*60)
    print(f"Output - Channels:  {nChanOut}")
    print(f"Output - Pols:      {nPol}")
    print("="*60)
    
    if args.dryrun:
        print("\nThis was a dry-run. No output written.")
        sys.exit(0)
    
    # Open input table for reading
    print("\nOpening input MS...")
    tfIn = table(inputMS, readonly=True, ack=False)
    
    # Read all data and average
    if averageAllBaselines:
        print(f"Reading and averaging data for ALL cross-correlation baselines (excluding autos)...")
        
        # First, identify which baselines are cross-correlations
        # Read ANTENNA1 and ANTENNA2 for first record to identify baselines
        antenna1 = tfIn.getcol('ANTENNA1', startrow=0, nrow=nBase, rowincr=1)
        antenna2 = tfIn.getcol('ANTENNA2', startrow=0, nrow=nBase, rowincr=1)
        
        # Find cross-correlation baselines (a1 != a2)
        crossCorrMask = antenna1 != antenna2
        crossCorrIndices = np.where(crossCorrMask)[0]
        nCrossCorr = len(crossCorrIndices)
        
        print(f"Found {nCrossCorr} cross-correlation baselines (excluding {nBase - nCrossCorr} auto-correlations)")
        
        # Collect data for all cross-correlation baselines and all time records
        allData = []
        allFlags = []
        
        for iRec in range(nRec):
            for iBase in crossCorrIndices:
                rowNum = iRec * nBase + iBase
                data = tfIn.getcell('DATA', rowNum)  # [nChan, nPol]
                flag = tfIn.getcell('FLAG', rowNum)  # [nChan, nPol]
                allData.append(data)
                allFlags.append(flag)
        
        tfIn.close()
        
        # Stack into arrays: [nRec * nCrossCorr, nChan, nPol]
        allData = np.array(allData)
        allFlags = np.array(allFlags)
        
        print(f"Data shape: {allData.shape}")
        
        # Reshape to [nRec, nCrossCorr, nChan, nPol] for proper averaging
        allData = allData.reshape(nRec, nCrossCorr, nChan, nPol)
        allFlags = allFlags.reshape(nRec, nCrossCorr, nChan, nPol)
        
        # Average over time and baselines together
        # First average over baselines for each time
        baseAvgData = []
        baseAvgFlags = []
        
        for iRec in range(nRec):
            recData = allData[iRec, :, :, :]  # [nBase, nChan, nPol]
            recFlags = allFlags[iRec, :, :, :]
            
            # Create masked array for baseline averaging
            mask = ~recFlags
            masked_data = np.ma.array(recData, mask=~mask)
            # Average over baselines (axis 0)
            avg_rec_data = np.ma.mean(masked_data, axis=0).filled(0)  # [nChan, nPol]
            avg_rec_flags = np.all(recFlags, axis=0)  # [nChan, nPol]
            
            baseAvgData.append(avg_rec_data)
            baseAvgFlags.append(avg_rec_flags)
        
        # Stack: [nRec, nChan, nPol]
        allData = np.array(baseAvgData)
        allFlags = np.array(baseAvgFlags)
        
        print(f"Baseline-averaged data shape: {allData.shape}")
        
        # Now average over time and frequency
        avgData, avgFlags = average_data(allData, allFlags, timeAvg, freqAvg)
        
    else:
        print(f"Reading and averaging data for baseline {antNum1}-{antNum2}...")
        
        # Collect data for all time records for this baseline
        allData = []
        allFlags = []
        
        for iRec in range(nRec):
            rowNum = iRec * nBase + refBaseNum
            data = tfIn.getcell('DATA', rowNum)  # [nChan, nPol]
            flag = tfIn.getcell('FLAG', rowNum)  # [nChan, nPol]
            allData.append(data)
            allFlags.append(flag)
        
        tfIn.close()
        
        # Stack into arrays: [nRec, nChan, nPol]
        allData = np.array(allData)
        allFlags = np.array(allFlags)
        
        print(f"Data shape: {allData.shape}")
        
        # Average over time and frequency
        avgData, avgFlags = average_data(allData, allFlags, timeAvg, freqAvg)
    
    print(f"Averaged data shape: {avgData.shape}")
    
    # Convert polarization if requested
    if polMode == 'stokes':
        print("Converting to Stokes parameters...")
        avgData = linear_to_stokes(avgData)
        polLabels = ['I', 'Q', 'U', 'V']
    else:
        polLabels = ['XX', 'XY', 'YX', 'YY']
    
    # Write output text file
    print(f"\nWriting output to: {outputFile}")
    
    with open(outputFile, 'w') as f:
        # Write header
        f.write(f"# Averaged spectrum from: {inputMS}\n")
        f.write(f"# Baseline: {baselineLabel}\n")
        f.write(f"# Time averaging: {timeAvg} integrations\n")
        f.write(f"# Frequency averaging: {freqAvg} channels\n")
        f.write(f"# Polarization mode: {polMode}\n")
        f.write(f"# Telescope: {msInfo['telescope']}\n")
        f.write(f"# Reference Frequency: {msInfo['refFreq']} Hz\n")
        f.write(f"# Channel Width: {msInfo['chanWidth'][0]} Hz\n")
        f.write(f"#\n")
        f.write(f"# Column format:\n")
        f.write(f"# Chan")
        for pol in polLabels:
            f.write(f"  {pol}_Real  {pol}_Imag")
        f.write("\n")
        f.write("#" + "-"*79 + "\n")
        
        # Write data
        for iChan in range(nChanOut):
            f.write(f"{iChan:6d}")
            for iPol in range(nPol):
                re = np.real(avgData[iChan, iPol])
                im = np.imag(avgData[iChan, iPol])
                f.write(f"  {re:12.6e}  {im:12.6e}")
            f.write("\n")
    
    print("\n" + "="*60)
    print("SPECTRUM EXTRACTION COMPLETE")
    print("="*60)
    print(f"Output written to: {outputFile}")
    print(f"Channels: {nChanOut}")
    print(f"Polarizations: {polMode} ({', '.join(polLabels)})")
    print("="*60)
    
    # Determine which plots to generate (always generate default plots)
    if polMode == 'stokes':
        plotTypes = ['stokes', 'pol-degree']
    else:
        plotTypes = ['linear-combined']  # Single 2x2 plot for linear
    
    # Generate plots
    figures = []  # Store figures for showing later
    for plotType in plotTypes:
        print(f"\nGenerating {plotType} plot...")
        
        # Determine plot output filename
        if args.plot_file:
            # If custom filename provided, append plot type
            base = os.path.splitext(args.plot_file)[0]
            ext = os.path.splitext(args.plot_file)[1] or '.png'
            plotFile = f"{base}_{plotType}{ext}"
        else:
            # Auto-generate from output filename
            base = os.path.splitext(outputFile)[0]
            plotFile = f"{base}_{plotType}.png"
        
        # Get channel frequencies for x-axis
        chanFreqs = msInfo['refFreq'] + np.arange(nChanOut) * msInfo['chanWidth'][0] * freqAvg
        chanFreqs_MHz = chanFreqs / 1e6  # Convert to MHz
        
        # Set up colors for each polarization
        if polMode == 'stokes':
            colors = {'I': 'black', 'Q': 'red', 'U': 'blue', 'V': 'green'}
        else:
            colors = {'XX': 'blue', 'XY': 'orange', 'YX': 'green', 'YY': 'red'}
        
        if plotType == 'linear-combined':
            # Plot all linear components in 2x2 subplots (Real, Imag, Amp, Phase)
            fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(14, 10))
            
            for iPol, pol in enumerate(polLabels):
                data = avgData[:, iPol]
                
                # Real
                ax1.plot(chanFreqs_MHz, np.real(data), label=pol, color=colors[pol], linewidth=1.5)
                # Imaginary
                ax2.plot(chanFreqs_MHz, np.imag(data), label=pol, color=colors[pol], linewidth=1.5)
                # Amplitude
                ax3.plot(chanFreqs_MHz, np.abs(data), label=pol, color=colors[pol], linewidth=1.5)
                # Phase
                ax4.plot(chanFreqs_MHz, np.angle(data, deg=True), label=pol, color=colors[pol], linewidth=1.5)
            
            # Configure subplots
            ax1.set_ylabel('Real', fontsize=12)
            ax1.grid(True, alpha=0.3)
            ax1.legend(loc='best', fontsize=9)
            ax1.set_title('Real Part', fontsize=12)
            
            ax2.set_ylabel('Imaginary', fontsize=12)
            ax2.grid(True, alpha=0.3)
            ax2.legend(loc='best', fontsize=9)
            ax2.set_title('Imaginary Part', fontsize=12)
            
            ax3.set_ylabel('Amplitude', fontsize=12)
            ax3.set_xlabel('Frequency (MHz)', fontsize=12)
            ax3.grid(True, alpha=0.3)
            ax3.legend(loc='best', fontsize=9)
            ax3.set_title('Amplitude', fontsize=12)
            
            ax4.set_ylabel('Phase (degrees)', fontsize=12)
            ax4.set_xlabel('Frequency (MHz)', fontsize=12)
            ax4.grid(True, alpha=0.3)
            ax4.legend(loc='best', fontsize=9)
            ax4.set_ylim(-180, 180)
            ax4.set_title('Phase', fontsize=12)
            
            fig.suptitle(f'Averaged Spectrum: {polMode.upper()} (Beam {msInfo["beamNum"]}, Baseline {baselineLabel})', fontsize=14, y=0.995)
            
            plt.tight_layout()
            plt.savefig(plotFile, dpi=150, bbox_inches='tight')
            print(f"Plot saved to: {plotFile}")
            
            if args.show_plot:
                figures.append(fig)
            else:
                plt.close()
            
        elif plotType == 'real-imag':
            
            for iPol, pol in enumerate(polLabels):
                data = avgData[:, iPol]
                ax1.plot(chanFreqs_MHz, np.real(data), label=pol, color=colors[pol], linewidth=1.5)
                ax2.plot(chanFreqs_MHz, np.imag(data), label=pol, color=colors[pol], linewidth=1.5)
            
            ax1.set_ylabel('Real', fontsize=12)
            ax1.grid(True, alpha=0.3)
            ax1.legend(loc='best', fontsize=10)
            ax1.set_title(f'Averaged Spectrum: {polMode.upper()} (Beam {msInfo["beamNum"]}, Baseline {baselineLabel})', fontsize=14)
            
            ax2.set_ylabel('Imaginary', fontsize=12)
            ax2.set_xlabel('Frequency (MHz)', fontsize=12)
            ax2.grid(True, alpha=0.3)
            ax2.legend(loc='best', fontsize=10)
            
            plt.tight_layout()
            plt.savefig(plotFile, dpi=150, bbox_inches='tight')
            print(f"Plot saved to: {plotFile}")
            
            if args.show_plot:
                figures.append(fig)
            else:
                plt.close()
            
        elif plotType == 'amp-phase':
            # Plot amplitude and phase
            fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8))
            
            for iPol, pol in enumerate(polLabels):
                data = avgData[:, iPol]
                amp = np.abs(data)
                phase = np.angle(data, deg=True)
                
                ax1.plot(chanFreqs_MHz, amp, label=pol, color=colors[pol], linewidth=1.5)
                ax2.plot(chanFreqs_MHz, phase, label=pol, color=colors[pol], linewidth=1.5)
            
            ax1.set_ylabel('Amplitude', fontsize=12)
            ax1.grid(True, alpha=0.3)
            ax1.legend(loc='best', fontsize=10)
            ax1.set_title(f'Averaged Spectrum: {polMode.upper()} (Beam {msInfo["beamNum"]}, Baseline {baselineLabel})', fontsize=14)
            
            ax2.set_ylabel('Phase (degrees)', fontsize=12)
            ax2.set_xlabel('Frequency (MHz)', fontsize=12)
            ax2.grid(True, alpha=0.3)
            ax2.legend(loc='best', fontsize=10)
            ax2.set_ylim(-180, 180)
            
            plt.tight_layout()
            plt.savefig(plotFile, dpi=150, bbox_inches='tight')
            print(f"Plot saved to: {plotFile}")
            
            if args.show_plot:
                figures.append(fig)
            else:
                plt.close()
            
        elif plotType == 'stokes':
            # Plot Stokes parameters (real values only)
            if polMode != 'stokes':
                print("WARNING: --plot stokes only works with --pol-mode stokes")
                print("Skipping stokes plot.")
            else:
                fig, ax = plt.subplots(1, 1, figsize=(12, 6))
                
                for iPol, pol in enumerate(polLabels):
                    data = avgData[:, iPol]
                    # Stokes parameters should be real-valued
                    realData = np.real(data)
                    ax.plot(chanFreqs_MHz, realData, label=pol, color=colors[pol], linewidth=1.5)
                
                ax.set_ylabel('Stokes Value', fontsize=12)
                ax.set_xlabel('Frequency (MHz)', fontsize=12)
                ax.grid(True, alpha=0.3)
                ax.legend(loc='best', fontsize=10)
                ax.set_title(f'Averaged Spectrum: Stokes Parameters (Beam {msInfo["beamNum"]}, Baseline {baselineLabel})', fontsize=14)
                
                plt.tight_layout()
                plt.savefig(plotFile, dpi=150, bbox_inches='tight')
                print(f"Plot saved to: {plotFile}")
                
                if args.show_plot:
                    figures.append(fig)
                else:
                    plt.close()
        
        elif plotType == 'pol-degree':
            # Plot polarization degree (percentage)
            if polMode != 'stokes':
                print("WARNING: --plot pol-degree only works with --pol-mode stokes")
                print("Skipping pol-degree plot.")
            else:
                # Extract Stokes parameters (real values)
                I = np.real(avgData[:, 0])
                Q = np.real(avgData[:, 1])
                U = np.real(avgData[:, 2])
                V = np.real(avgData[:, 3])
                
                # Calculate polarization degrees (in percentage)
                # Avoid division by zero
                I_safe = np.where(I != 0, I, np.nan)
                
                pol_Q = (Q / I_safe) * 100  # Linear Q polarization degree
                pol_U = (U / I_safe) * 100  # Linear U polarization degree
                pol_L = (np.sqrt(Q**2 + U**2) / I_safe) * 100  # Total linear polarization degree
                pol_V = (V / I_safe) * 100  # Circular polarization degree
                
                # Calculate median values using absolute values (ignoring NaNs)
                median_Q = np.nanmedian(np.abs(pol_Q))
                median_U = np.nanmedian(np.abs(pol_U))
                median_L = np.nanmedian(pol_L)  # Already positive (sqrt)
                median_V = np.nanmedian(np.abs(pol_V))
                
                # Create plot
                fig, ax = plt.subplots(1, 1, figsize=(12, 6))
                
                ax.plot(chanFreqs_MHz, pol_Q, label='Q/I', color='red', linewidth=1.5, alpha=0.8)
                ax.plot(chanFreqs_MHz, pol_U, label='U/I', color='blue', linewidth=1.5, alpha=0.8)
                ax.plot(chanFreqs_MHz, pol_L, label='√(Q²+U²)/I', color='purple', linewidth=2.0, alpha=0.9)
                ax.plot(chanFreqs_MHz, pol_V, label='V/I', color='green', linewidth=1.5, alpha=0.8)
                
                ax.set_ylabel('Polarization Degree (%)', fontsize=12)
                ax.set_xlabel('Frequency (MHz)', fontsize=12)
                ax.grid(True, alpha=0.3)
                ax.legend(loc='best', fontsize=10)
                ax.set_title(f'Polarization Degree (Beam {msInfo["beamNum"]}, Baseline {baselineLabel})', fontsize=14)
                
                # Set y-axis limits if specified, otherwise auto-scale
                if args.ylim_pol is not None:
                    ax.set_ylim(args.ylim_pol[0], args.ylim_pol[1])
                
                # Add text box with median values
                textstr = '\n'.join([
                    'Median Values:',
                    f'|Q|/I = {median_Q:.3f}%',
                    f'|U|/I = {median_U:.3f}%',
                    f'√(Q²+U²)/I = {median_L:.3f}%',
                    f'|V|/I = {median_V:.3f}%'
                ])
                props = dict(boxstyle='round', facecolor='lightgreen', alpha=0.9)
                ax.text(0.02, 0.98, textstr, transform=ax.transAxes, fontsize=10,
                       verticalalignment='top', bbox=props)
                
                plt.tight_layout()
                plt.savefig(plotFile, dpi=150, bbox_inches='tight')
                print(f"Plot saved to: {plotFile}")
                print(f"\nMedian Polarization Degrees:")
                print(f"  |Q|/I = {median_Q:.3f}%")
                print(f"  |U|/I = {median_U:.3f}%")
                print(f"  √(Q²+U²)/I = {median_L:.3f}%")
                print(f"  |V|/I = {median_V:.3f}%")
                
                if args.show_plot:
                    figures.append(fig)
                else:
                    plt.close()
    
    # Show all figures at once if requested
    if args.show_plot and figures:
        plt.show()
        
    print("="*60)
