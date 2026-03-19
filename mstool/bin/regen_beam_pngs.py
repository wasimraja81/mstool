#!/usr/bin/env python
"""
Regenerate per-beam spectrum PNG plots from averaged spectrum .txt files produced
by averageMS.py — without needing the original measurement sets.

The .txt files contain the full per-channel complex data in their body, plus all
metadata (reference frequency, channel width, SB tags, polarization mode) in their
header.  This script reads those files and produces pixel-for-pixel identical plots
to what averageMS.py would have generated on the HPC.

Usage examples
--------------
# Single file:
    python regen_beam_pngs.py beam00.allcross.tavgAll.favg4.stokes.txt

# Using short flag:
    python regen_beam_pngs.py -i /path/to/outputs/ --overwrite

# All beam txt files in a directory (bpcal + lcal):
    python regen_beam_pngs.py /path/to/outputs/

# Override y-axis limits for pol-degree panels:
    python regen_beam_pngs.py /path/to/outputs/ --ylim-pol -5 5

                                     --wr, Mar 2026
"""

import os
import sys
import re
import glob
import argparse
import numpy as np
import matplotlib.pyplot as plt


# ---------------------------------------------------------------------------
# Shared plot helpers (identical to averageMS.py)
# ---------------------------------------------------------------------------

def apply_plot_header(fig, main_title, plot_tag_text, field_name=''):
    fig.suptitle(main_title, fontsize=14, fontweight='bold', y=0.985)

    parts = [part.strip() for part in str(plot_tag_text).split(',') if part.strip()]
    tag_text = "   |   ".join(parts)
    fig.text(
        0.5, 0.905, tag_text,
        ha='center', va='center', fontsize=9.5, color='midnightblue',
        bbox=dict(boxstyle='round,pad=0.22', facecolor='lavender',
                  edgecolor='slateblue', alpha=0.92)
    )

    field_name_text = str(field_name or '').strip()
    if field_name_text:
        fig.text(
            0.5, 0.865, f"SB_REF FIELD_NAME: {field_name_text}",
            ha='center', va='center', fontsize=9.2, color='darkgreen',
            bbox=dict(boxstyle='round,pad=0.20', facecolor='honeydew',
                      edgecolor='seagreen', alpha=0.90)
        )
    else:
        fig.text(0.5, 0.865, ' ', ha='center', va='center', fontsize=9.2)


# ---------------------------------------------------------------------------
# .txt parser
# ---------------------------------------------------------------------------

def parse_txt_file(txt_file):
    """
    Parse an averageMS.py output .txt file.

    Returns
    -------
    meta : dict
        All header metadata.
    avgData : ndarray, shape (nChan, nPol), complex128
        Reconstructed per-channel complex data.
    """
    meta = {
        'polMode': 'stokes',
        'refFreq': None,
        'chanWidth': None,
        'baseline': 'unknown',
        'telescope': 'unknown',
        'sb_ref': 'NA',
        'sb_1934': 'NA',
        'sb_holo': 'NA',
        'sb_target_1934': 'NA',
        'time_avg': None,
        'freq_avg': None,
        'source_ms': None,
    }

    data_rows = []
    with open(txt_file, 'r') as f:
        for line in f:
            line = line.rstrip('\n')
            if line.startswith('#'):
                # Strip leading '#' and optional spaces
                content = line.lstrip('#').strip()
                if content.startswith('-'):
                    continue  # separator line

                # Key: value parsing
                if ':' in content:
                    key, _, val = content.partition(':')
                    key = key.strip()
                    val = val.strip()

                    if key == 'Polarization mode':
                        meta['polMode'] = val
                    elif key == 'Reference Frequency':
                        # "1.3e+09 Hz" → float
                        meta['refFreq'] = float(val.split()[0])
                    elif key == 'Channel Width':
                        meta['chanWidth'] = float(val.split()[0])
                    elif key == 'Baseline':
                        meta['baseline'] = val
                    elif key == 'Telescope':
                        meta['telescope'] = val
                    elif key == 'SB_REF':
                        meta['sb_ref'] = val
                    elif key == 'SB_1934':
                        meta['sb_1934'] = val
                    elif key == 'SB_HOLO':
                        meta['sb_holo'] = val
                    elif key == 'SB_TARGET_1934':
                        meta['sb_target_1934'] = val
                    elif key == 'Time averaging':
                        try:
                            meta['time_avg'] = int(val.split()[0])
                        except ValueError:
                            pass
                    elif key == 'Frequency averaging':
                        try:
                            meta['freq_avg'] = int(val.split()[0])
                        except ValueError:
                            pass
                    elif key == 'Averaged spectrum from':
                        meta['source_ms'] = val
            else:
                stripped = line.strip()
                if stripped == '':
                    continue
                parts = stripped.split()
                if len(parts) >= 3:
                    try:
                        int(parts[0])   # channel index
                        data_rows.append([float(v) for v in parts[1:]])
                    except (ValueError, IndexError):
                        pass  # skip column-header lines that start with 'Chan'

    if not data_rows:
        raise ValueError(f"No data rows found in {txt_file}")

    arr = np.array(data_rows, dtype=np.float64)
    nChan, nCols = arr.shape
    nPol = nCols // 2

    avgData = np.zeros((nChan, nPol), dtype=np.complex128)
    for iPol in range(nPol):
        avgData[:, iPol] = arr[:, 2 * iPol] + 1j * arr[:, 2 * iPol + 1]

    return meta, avgData


def _beam_num_from_filename(txt_file):
    """Extract beam number from filename, e.g. 'beam06' → 6, or return None."""
    m = re.search(r'beam(\d+)', os.path.basename(txt_file), re.IGNORECASE)
    return int(m.group(1)) if m else None


def _build_plot_tag_text(meta):
    """Rebuild the multi-tag header line from parsed metadata."""
    def _fmt(prefix, num):
        if num and num != 'NA':
            return f"{prefix}{num}"
        return f"{prefix}NA"

    parts = [
        _fmt('SB_REF-', meta['sb_ref']),
        _fmt('SB_1934-', meta['sb_1934']),
        _fmt('SB_HOLO-', meta['sb_holo']),
        _fmt('SB_TARGET_1934-', meta['sb_target_1934']),
    ]
    return ', '.join(parts)


# ---------------------------------------------------------------------------
# Core PNG generator — shared with combine_beam_outputs.py
# ---------------------------------------------------------------------------

def generate_pngs_from_txt(
    txt_file,
    output_dir=None,
    overwrite=False,
    ylim_pol=None,
    field_name='',
    verbose=True,
):
    """
    Read *txt_file* (an averageMS.py output) and write per-beam spectrum PNGs
    identical to those averageMS.py would have produced.

    Parameters
    ----------
    txt_file : str
        Path to the .txt file.
    output_dir : str or None
        Directory in which to write PNGs.  Defaults to same directory as txt_file.
    overwrite : bool
        If False (default), skip generation when the PNG already exists.
    ylim_pol : (float, float) or None
        Y-axis limits for the pol-degree panel (percent).  None = auto.
    field_name : str
        Optional field-name label shown in the plot header.
    verbose : bool
        Print progress messages.

    Returns
    -------
    list[str]
        Paths of PNG files written (empty if all were skipped).
    """
    if output_dir is None:
        output_dir = os.path.dirname(os.path.abspath(txt_file))

    meta, avgData = parse_txt_file(txt_file)
    polMode = meta['polMode']
    nChan, nPol = avgData.shape

    if polMode == 'stokes':
        polLabels = ['I', 'Q', 'U', 'V']
        plotTypes = ['stokes', 'pol-degree']
    else:
        polLabels = ['XX', 'XY', 'YX', 'YY']
        plotTypes = ['linear-combined']

    # Validate nPol consistency
    expected_nPol = len(polLabels)
    if nPol != expected_nPol:
        raise ValueError(
            f"{txt_file}: expected {expected_nPol} polarizations for {polMode} "
            f"mode, got {nPol} columns"
        )

    # Frequency axis
    if meta['refFreq'] is None or meta['chanWidth'] is None:
        raise ValueError(f"{txt_file}: missing Reference Frequency or Channel Width in header")
    chanFreqs_MHz = (meta['refFreq'] + np.arange(nChan) * meta['chanWidth']) / 1e6

    # Metadata for plot headers
    beam_num = _beam_num_from_filename(txt_file)
    baseline_label = meta['baseline']
    plot_tag_text = _build_plot_tag_text(meta)

    # Base name for outputs (strip .txt suffix)
    txt_stem = os.path.splitext(os.path.basename(txt_file))[0]
    base_out = os.path.join(output_dir, txt_stem)

    # Colors
    if polMode == 'stokes':
        colors = {'I': 'black', 'Q': 'red', 'U': 'blue', 'V': 'green'}
    else:
        colors = {'XX': 'blue', 'XY': 'orange', 'YX': 'green', 'YY': 'red'}

    written = []

    for plotType in plotTypes:
        plot_file = f"{base_out}_{plotType}.png"

        if not overwrite and os.path.exists(plot_file):
            if verbose:
                print(f"  [skip] {os.path.basename(plot_file)} already exists")
            continue

        if verbose:
            print(f"  Generating {plotType} → {os.path.basename(plot_file)}")

        # ------------------------------------------------------------------
        # stokes plot
        # ------------------------------------------------------------------
        if plotType == 'stokes':
            fig, ax = plt.subplots(1, 1, figsize=(12, 6))

            for iPol, pol in enumerate(polLabels):
                realData = np.real(avgData[:, iPol])
                ax.plot(chanFreqs_MHz, realData, label=pol, color=colors[pol], linewidth=1.5)

            ax.set_ylabel('Stokes Value', fontsize=12)
            ax.set_xlabel('Frequency (MHz)', fontsize=12)
            ax.grid(True, alpha=0.3)
            ax.legend(loc='best', fontsize=10)
            beam_str = f"Beam {beam_num}" if beam_num is not None else "Beam ?"
            apply_plot_header(
                fig,
                f'Averaged Spectrum: Stokes Parameters ({beam_str}, Baseline {baseline_label})',
                plot_tag_text,
                field_name,
            )
            plt.tight_layout(rect=[0, 0, 1, 0.83])
            plt.savefig(plot_file, dpi=150, bbox_inches='tight')
            plt.close()
            written.append(plot_file)

        # ------------------------------------------------------------------
        # pol-degree plot
        # ------------------------------------------------------------------
        elif plotType == 'pol-degree':
            I = np.real(avgData[:, 0])
            Q = np.real(avgData[:, 1])
            U = np.real(avgData[:, 2])
            V = np.real(avgData[:, 3])

            I_safe = np.where(I != 0, I, np.nan)
            pol_Q = (Q / I_safe) * 100
            pol_U = (U / I_safe) * 100
            pol_L = (np.sqrt(Q**2 + U**2) / I_safe) * 100
            pol_V = (V / I_safe) * 100

            median_Q       = np.nanmedian(np.abs(pol_Q))
            median_U       = np.nanmedian(np.abs(pol_U))
            median_L       = np.nanmedian(pol_L)
            median_V       = np.nanmedian(np.abs(pol_V))
            median_Q_signed = np.nanmedian(pol_Q)
            median_U_signed = np.nanmedian(pol_U)
            median_V_signed = np.nanmedian(pol_V)
            mad_Q = np.nanmedian(np.abs(pol_Q - median_Q_signed))
            mad_U = np.nanmedian(np.abs(pol_U - median_U_signed))
            mad_V = np.nanmedian(np.abs(pol_V - median_V_signed))
            mad_L = np.nanmedian(np.abs(pol_L - median_L))

            fig, ax = plt.subplots(1, 1, figsize=(12, 6))
            ax.plot(chanFreqs_MHz, pol_Q, label='Q/I', color='red',    linewidth=1.5, alpha=0.8)
            ax.plot(chanFreqs_MHz, pol_U, label='U/I', color='blue',   linewidth=1.5, alpha=0.8)
            ax.plot(chanFreqs_MHz, pol_L, label='√(Q²+U²)/I', color='purple', linewidth=2.0, alpha=0.9)
            ax.plot(chanFreqs_MHz, pol_V, label='V/I', color='green',  linewidth=1.5, alpha=0.8)

            ax.set_ylabel('Polarization Degree (%)', fontsize=12)
            ax.set_xlabel('Frequency (MHz)', fontsize=12)
            ax.grid(True, alpha=0.3)
            ax.legend(loc='best', fontsize=10)

            if ylim_pol is not None:
                ax.set_ylim(ylim_pol[0], ylim_pol[1])

            beam_str = f"Beam {beam_num}" if beam_num is not None else "Beam ?"
            apply_plot_header(
                fig,
                f'Polarization Degree ({beam_str}, Baseline {baseline_label})',
                plot_tag_text,
                field_name,
            )

            textstr = '\n'.join([
                'Median Values:',
                f'|Q|/I = {median_Q:.3f}%',
                f'|U|/I = {median_U:.3f}%',
                f'√(Q²+U²)/I = {median_L:.3f}%',
                f'|V|/I = {median_V:.3f}%',
                '',
                'Additional (median ± MAD):',
                f'Q/I={median_Q_signed:+.3f}±{mad_Q:.3f}, '
                f'U/I={median_U_signed:+.3f}±{mad_U:.3f}, '
                f'V/I={median_V_signed:+.3f}±{mad_V:.3f}%',
                f'√(Q²+U²)/I={median_L:.3f}±{mad_L:.3f}%',
            ])
            props = dict(boxstyle='round', facecolor='lightgreen', alpha=0.9)
            ax.text(0.02, 0.98, textstr, transform=ax.transAxes, fontsize=10,
                    verticalalignment='top', bbox=props)

            plt.tight_layout(rect=[0, 0, 1, 0.83])
            plt.savefig(plot_file, dpi=150, bbox_inches='tight')
            plt.close()
            written.append(plot_file)

        # ------------------------------------------------------------------
        # linear-combined (2×2: real, imag, amp, phase)
        # ------------------------------------------------------------------
        elif plotType == 'linear-combined':
            fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(14, 10))

            for iPol, pol in enumerate(polLabels):
                data = avgData[:, iPol]
                ax1.plot(chanFreqs_MHz, np.real(data),            label=pol, color=colors[pol], linewidth=1.5)
                ax2.plot(chanFreqs_MHz, np.imag(data),            label=pol, color=colors[pol], linewidth=1.5)
                ax3.plot(chanFreqs_MHz, np.abs(data),             label=pol, color=colors[pol], linewidth=1.5)
                ax4.plot(chanFreqs_MHz, np.angle(data, deg=True), label=pol, color=colors[pol], linewidth=1.5)

            ax1.set_ylabel('Real', fontsize=12);       ax1.grid(True, alpha=0.3); ax1.legend(loc='best', fontsize=9); ax1.set_title('Real Part', fontsize=12)
            ax2.set_ylabel('Imaginary', fontsize=12);  ax2.grid(True, alpha=0.3); ax2.legend(loc='best', fontsize=9); ax2.set_title('Imaginary Part', fontsize=12)
            ax3.set_ylabel('Amplitude', fontsize=12);  ax3.set_xlabel('Frequency (MHz)', fontsize=12); ax3.grid(True, alpha=0.3); ax3.legend(loc='best', fontsize=9); ax3.set_title('Amplitude', fontsize=12)
            ax4.set_ylabel('Phase (degrees)', fontsize=12); ax4.set_xlabel('Frequency (MHz)', fontsize=12); ax4.grid(True, alpha=0.3); ax4.legend(loc='best', fontsize=9); ax4.set_ylim(-180, 180); ax4.set_title('Phase', fontsize=12)

            beam_str = f"Beam {beam_num}" if beam_num is not None else "Beam ?"
            apply_plot_header(
                fig,
                f'Averaged Spectrum: LINEAR (Beam {beam_num}, Baseline {baseline_label})',
                plot_tag_text,
                field_name,
            )
            plt.tight_layout(rect=[0, 0, 1, 0.83])
            plt.savefig(plot_file, dpi=150, bbox_inches='tight')
            plt.close()
            written.append(plot_file)

    return written


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args():
    p = argparse.ArgumentParser(
        description='Regenerate per-beam spectrum PNGs from averageMS.py .txt files.'
    )
    p.add_argument(
        'inputs', nargs='+',
        help='One or more .txt files, or a directory containing .txt files.'
    )
    p.add_argument(
        '-o', '--output-dir',
        default=None,
        help='Output directory for PNGs (default: same directory as each .txt file).'
    )
    p.add_argument(
        '--overwrite', action='store_true',
        help='Overwrite existing PNGs (default: skip if PNG already exists).'
    )
    p.add_argument(
        '--ylim-pol', dest='ylim_pol', nargs=2, type=float, default=None,
        metavar=('YMIN', 'YMAX'),
        help='Y-axis limits for pol-degree plots in percent (default: auto).'
    )
    p.add_argument(
        '--field-name', dest='field_name', default='',
        help='Optional SB_REF field name shown as a third header row on plots.'
    )
    p.add_argument(
        '--lcal', action='store_true',
        help='When a directory is given, also process .lcal.txt files (default: all .txt).'
    )
    return p.parse_args()


def collect_txt_files(inputs):
    """Expand paths: directories → glob *.txt; files → use directly."""
    collected = []
    for inp in inputs:
        if os.path.isdir(inp):
            collected.extend(sorted(glob.glob(os.path.join(inp, '*.txt'))))
        elif os.path.isfile(inp):
            collected.append(inp)
        else:
            # Treat as glob
            matches = sorted(glob.glob(inp))
            if matches:
                collected.extend(matches)
            else:
                print(f"WARNING: no files matched: {inp}", file=sys.stderr)
    # Deduplicate preserving order
    seen = set()
    out = []
    for f in collected:
        af = os.path.abspath(f)
        if af not in seen:
            seen.add(af)
            out.append(f)
    return out


def main():
    args = parse_args()
    txt_files = collect_txt_files(args.inputs)

    if not txt_files:
        print("ERROR: no .txt files found.", file=sys.stderr)
        sys.exit(1)

    total_written = 0
    total_skipped = 0
    total_errors  = 0

    for txt_file in txt_files:
        print(f"\n{'='*60}")
        print(f"Processing: {txt_file}")
        try:
            written = generate_pngs_from_txt(
                txt_file,
                output_dir=args.output_dir,
                overwrite=args.overwrite,
                ylim_pol=args.ylim_pol,
                field_name=args.field_name,
                verbose=True,
            )
            total_written += len(written)
            if not written:
                total_skipped += 1
        except Exception as e:
            print(f"  ERROR: {e}", file=sys.stderr)
            total_errors += 1

    print(f"\n{'='*60}")
    print(f"Done.  PNGs written: {total_written}  |  Files skipped: {total_skipped}  |  Errors: {total_errors}")


if __name__ == '__main__':
    main()
