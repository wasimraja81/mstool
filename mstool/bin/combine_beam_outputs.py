#!/usr/bin/env python

import os
import sys
import glob
import re
import argparse
import hashlib
from pathlib import Path
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.image as mpimg
from matplotlib.backends.backend_pdf import PdfPages

plt.rcParams['pdf.compression'] = 0

"""
Script to combine beam outputs from averageMS.py:
1. Create 6x6 grid PDFs combining stokes and pol-degree plots for all beams
2. Create MP4 and GIF animations showing beams in sequence
3. Extract and plot leakage statistics from text files

Usage: python combine_beam_outputs.py <output_directory>

                                     --wr, 25 Nov, 2025
"""


def parse_args():
    parser = argparse.ArgumentParser(
        description="Combine averageMS.py beam outputs into summary products."
    )
    parser.add_argument(
        "output_directory",
        help="Directory containing per-beam outputs (txt/png)"
    )
    parser.add_argument(
        "--output-prefix",
        default=None,
        help="Explicit prefix for generated outputs (overrides auto naming)",
    )
    parser.add_argument(
        "--name-template",
        default="{tag_sb_ref}__{tag_sb_1934}__{tag_sb_holo}__{tag_sb_target_1934}__{dataset}",
        help=(
            "Template for auto prefix using tokens: "
            "{sb_ref}, {proc}, {dataset}, {sb_ref_id}, {proc_sb}, "
            "{tag_sb_ref}, {tag_sb_1934}, {tag_sb_holo}, {tag_sb_target_1934}. "
            "Ignored when --output-prefix or --legacy-names is used."
        ),
    )
    parser.add_argument(
        "--max-prefix-len",
        type=int,
        default=180,
        help="Maximum length of auto-generated prefix before truncation",
    )
    parser.add_argument(
        "--legacy-names",
        action="store_true",
        help="Use original fixed output names (combined_beams.pdf, etc.)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show which outputs would be generated without writing files",
    )
    parser.add_argument(
        "--sb-ref",
        dest="sb_ref_tag",
        default=None,
        help="Optional tag for SB_REF (e.g. SB_REF-81084) to include in output names",
    )
    parser.add_argument(
        "--sb-1934",
        dest="sb_1934_tag",
        default=None,
        help="Optional tag for SB_1934 (e.g. SB_1934-77045) to include in output names",
    )
    parser.add_argument(
        "--sb-holo",
        dest="sb_holo_tag",
        default=None,
        help="Optional tag for SB_HOLO (e.g. SB_HOLO-76554) to include in output names",
    )
    parser.add_argument(
        "--sb-target-1934",
        dest="sb_target_1934_tag",
        default=None,
        help="Optional tag for SB_TARGET_1934 (e.g. SB_TARGET_1934-81089) to include in output names",
    )
    parser.add_argument(
        "--field-name",
        dest="field_name",
        default=None,
        help="Optional SB_REF field name to show as a third header row on plots",
    )
    return parser.parse_args()


def sanitize_token(value):
    if value is None:
        return "unknown"
    value = str(value).strip()
    value = value.replace(' ', '-')
    value = re.sub(r'[^A-Za-z0-9._-]+', '-', value)
    value = re.sub(r'-{2,}', '-', value)
    value = re.sub(r'_{2,}', '_', value)
    value = value.strip('._-')
    return value or "unknown"


def normalize_tag_input(value, prefix):
    if value is None:
        return None
    raw = str(value).strip()
    if raw == "":
        return None
    if re.fullmatch(r'\d+', raw):
        return f"{prefix}{raw}"
    if raw.startswith(prefix):
        return raw
    return raw


def derive_dataset_tag(output_dir):
    txt_files = sorted(glob.glob(os.path.join(output_dir, "*.txt")))
    if len(txt_files) == 0:
        return "unknownDataset"

    # Prefer non-lcal file for base dataset identity
    preferred = [f for f in txt_files if '.lcal.txt' not in f]
    sample = preferred[0] if preferred else txt_files[0]

    stem = Path(sample).name
    if stem.endswith('.txt'):
        stem = stem[:-4]
    if stem.endswith('.lcal'):
        stem = stem[:-5]

    # Remove trailing beam markers (e.g. .beam00 or _beam0.beam00)
    stem = re.sub(r'([._-]beam\d+)+$', '', stem)
    # Remove trailing source-name token such as .B1934-638 (or _B1934-638)
    stem = re.sub(r'([._-]B\d{4}-\d+)$', '', stem)
    return sanitize_token(stem)


def derive_name_tokens(output_dir):
    out_path = Path(output_dir)
    proc_dir = out_path.parent.name if out_path.parent else "unknownProc"
    sb_ref = out_path.parent.parent.name if out_path.parent and out_path.parent.parent else "unknownSB"
    dataset = derive_dataset_tag(output_dir)

    sb_ref_id_match = re.search(r'SB_REF-([0-9]+)', sb_ref)
    proc_sb_match = re.search(r'SB-([0-9]+)', proc_dir)
    sb_1934_match = re.search(r'(SB_1934-[0-9]+)', sb_ref)
    sb_holo_match = re.search(r'(SB_HOLO-[0-9]+)', sb_ref)
    proc_target = f"SB_TARGET_1934-{proc_sb_match.group(1)}" if proc_sb_match else "unknownTarget"

    tokens = {
        'sb_ref': sanitize_token(sb_ref),
        'proc': sanitize_token(proc_target),
        'dataset': sanitize_token(dataset),
        'sb_ref_id': sb_ref_id_match.group(1) if sb_ref_id_match else "unknown",
        'proc_sb': proc_sb_match.group(1) if proc_sb_match else "unknown",
        'tag_sb_ref': sanitize_token(sb_ref_id_match.group(0) if sb_ref_id_match else "unknown"),
        'tag_sb_1934': sanitize_token(sb_1934_match.group(1) if sb_1934_match else "unknown"),
        'tag_sb_holo': sanitize_token(sb_holo_match.group(1) if sb_holo_match else "unknown"),
        'tag_sb_target_1934': sanitize_token(f"SB_TARGET_1934-{proc_sb_match.group(1)}" if proc_sb_match else "unknown"),
    }
    return tokens


def build_optional_param_tags(args):
    tags = []
    sb_ref_tag = normalize_tag_input(args.sb_ref_tag, "SB_REF-")
    sb_1934_tag = normalize_tag_input(args.sb_1934_tag, "SB_1934-")
    sb_holo_tag = normalize_tag_input(args.sb_holo_tag, "SB_HOLO-")
    sb_target_1934_tag = normalize_tag_input(args.sb_target_1934_tag, "SB_TARGET_1934-")

    if sb_ref_tag:
        tags.append(sanitize_token(sb_ref_tag))
    if sb_1934_tag:
        tags.append(sanitize_token(sb_1934_tag))
    if sb_holo_tag:
        tags.append(sanitize_token(sb_holo_tag))
    if sb_target_1934_tag:
        tags.append(sanitize_token(sb_target_1934_tag))
    return tags


def build_output_prefix(output_dir, explicit_prefix=None, template="{sb_ref}__{proc}__{dataset}",
                        max_len=180, legacy_names=False, extra_tags=None):
    if legacy_names:
        return ""

    if explicit_prefix:
        return sanitize_token(explicit_prefix)

    tokens = derive_name_tokens(output_dir)
    try:
        prefix = template.format(**tokens)
    except Exception as e:
        print(f"WARNING: Invalid --name-template ({e}), falling back to default")
        prefix = "{sb_ref}__{proc}__{dataset}".format(**tokens)

    prefix = sanitize_token(prefix)

    if extra_tags:
        unique_tags = []
        seen = set()
        for tag in extra_tags:
            clean_tag = sanitize_token(tag)
            if not clean_tag or clean_tag in seen:
                continue
            seen.add(clean_tag)
            unique_tags.append(clean_tag)

        tags_to_append = []
        for tag in unique_tags:
            # Avoid duplicating tags already present in the base prefix template
            pattern = rf'(^|[._-]){re.escape(tag)}($|[._-])'
            if re.search(pattern, prefix):
                continue
            tags_to_append.append(tag)

        extra = "__".join(tags_to_append)
        if extra:
            prefix = f"{prefix}__{extra}" if prefix else extra

    if len(prefix) > max_len:
        digest = hashlib.md5(prefix.encode('utf-8')).hexdigest()[:8]
        keep = max(16, max_len - 9)
        head = prefix[:keep].rstrip('._-')
        if not head:
            head = prefix[:keep]
        prefix = sanitize_token(f"{head}-{digest}")
    return prefix


def make_output_path(output_dir, prefix, stem, ext):
    if prefix:
        filename = f"{prefix}.{stem}{ext}"
    else:
        filename = f"{stem}{ext}"
    return os.path.join(output_dir, filename)


def resolve_plot_tags(tokens, args):
    sb_ref = normalize_tag_input(args.sb_ref_tag, "SB_REF-") or tokens.get('tag_sb_ref', 'unknown')
    sb_1934 = normalize_tag_input(args.sb_1934_tag, "SB_1934-") or tokens.get('tag_sb_1934', 'unknown')
    sb_holo = normalize_tag_input(args.sb_holo_tag, "SB_HOLO-") or tokens.get('tag_sb_holo', 'unknown')
    sb_target = normalize_tag_input(args.sb_target_1934_tag, "SB_TARGET_1934-") or tokens.get('tag_sb_target_1934', 'unknown')

    if sb_ref == 'unknown':
        sb_ref = 'SB_REF-NA'
    if sb_1934 == 'unknown':
        sb_1934 = 'SB_1934-NA'
    if sb_holo == 'unknown':
        sb_holo = 'SB_HOLO-NA'
    if sb_target == 'unknown':
        sb_target = 'SB_TARGET_1934-NA'

    return sb_ref, sb_1934, sb_holo, sb_target


def summarize_variant_inputs(output_dir, variant=''):
    if variant:
        stokes_pattern = os.path.join(output_dir, f"*beam??{variant}_stokes.png")
        poldeg_pattern = os.path.join(output_dir, f"*beam??{variant}_pol-degree.png")
        txt_pattern = os.path.join(output_dir, f"*beam??{variant}.txt")
    else:
        stokes_pattern = os.path.join(output_dir, "*beam??_stokes.png")
        poldeg_pattern = os.path.join(output_dir, "*beam??_pol-degree.png")
        txt_pattern = os.path.join(output_dir, "*beam??.txt")

    stokes_files = glob.glob(stokes_pattern)
    poldeg_files = glob.glob(poldeg_pattern)
    txt_files = glob.glob(txt_pattern)

    if not variant:
        stokes_files = [f for f in stokes_files if '.lcal' not in f]
        poldeg_files = [f for f in poldeg_files if '.lcal' not in f]
        txt_files = [f for f in txt_files if '.lcal' not in f]

    return stokes_files, poldeg_files, txt_files

def parse_leakage_stats(txt_file):
    """
    Parse leakage statistics from the header of a text file.
    
    Returns:
        dict with keys 'Q/I', 'U/I', 'L/I', 'V/I' or None if not found
    """
    stats = {}
    try:
        with open(txt_file, 'r') as f:
            for line in f:
                if not line.startswith('#'):
                    break
                if '|Q|/I' in line:
                    match = re.search(r'=\s*([\d.]+)%', line)
                    if match:
                        stats['Q/I'] = float(match.group(1))
                elif '|U|/I' in line:
                    match = re.search(r'=\s*([\d.]+)%', line)
                    if match:
                        stats['U/I'] = float(match.group(1))
                elif '√(Q²+U²)/I' in line or 'sqrt(Q' in line:
                    match = re.search(r'=\s*([\d.]+)%', line)
                    if match:
                        stats['L/I'] = float(match.group(1))
                elif '|V|/I' in line:
                    match = re.search(r'=\s*([\d.]+)%', line)
                    if match:
                        stats['V/I'] = float(match.group(1))
    except Exception as e:
        print(f"Warning: Could not parse {txt_file}: {e}")
        return None
    
    if len(stats) == 4:
        return stats
    else:
        return None


def create_combined_pdf(output_dir, variant='', output_prefix=''):
    """
    Create a PDF with 6x6 grids of plots.
    
    Args:
        output_dir: Directory containing the PNG files
        variant: '' for regular, '.lcal' for leakage calibrated
    
    Returns:
        PDF filename
    """
    # Find all stokes and pol-degree plots for this variant
    if variant:
        stokes_pattern = os.path.join(output_dir, f"*beam??{variant}_stokes.png")
        poldeg_pattern = os.path.join(output_dir, f"*beam??{variant}_pol-degree.png")
        pdf_name = make_output_path(output_dir, output_prefix, f"combined_beams{variant}", ".pdf")
        title_suffix = " (Leakage Calibrated)"
    else:
        stokes_pattern = os.path.join(output_dir, "*beam??_stokes.png")
        poldeg_pattern = os.path.join(output_dir, "*beam??_pol-degree.png")
        # Exclude .lcal files
        pdf_name = make_output_path(output_dir, output_prefix, "combined_beams", ".pdf")
        title_suffix = ""
    
    stokes_files = glob.glob(stokes_pattern)
    poldeg_files = glob.glob(poldeg_pattern)
    
    # Filter out .lcal files if we're looking for regular files
    if not variant:
        stokes_files = [f for f in stokes_files if '.lcal' not in f]
        poldeg_files = [f for f in poldeg_files if '.lcal' not in f]
    
    # Extract beam numbers and sort numerically
    def get_beam_num(filename):
        match = re.search(r'beam(\d+)', filename)
        return int(match.group(1)) if match else 999
    
    stokes_files = sorted(stokes_files, key=get_beam_num)
    poldeg_files = sorted(poldeg_files, key=get_beam_num)
    
    print(f"\nProcessing {variant if variant else 'regular'} variant:")
    print(f"  Found {len(stokes_files)} stokes plots")
    print(f"  Found {len(poldeg_files)} pol-degree plots")
    
    if len(stokes_files) == 0 or len(poldeg_files) == 0:
        print(f"  WARNING: No files found for variant '{variant}', skipping...")
        return None
    
    # Create PDF with multiple pages
    with PdfPages(pdf_name) as pdf:
        # Page 1: Stokes plots in 6x6 grid
        fig = plt.figure(figsize=(36, 36), dpi=300)
        fig.suptitle(f'Stokes Parameters - All Beams{title_suffix}', fontsize=20, y=0.995)
        
        for i, img_file in enumerate(stokes_files[:36]):  # Max 36 beams
            ax = fig.add_subplot(6, 6, i+1)
            img = mpimg.imread(img_file)
            ax.imshow(img, interpolation='none', resample=False)
            ax.axis('off')
            
            # Extract beam number from filename
            beam_num = get_beam_num(img_file)
            ax.set_title(f'Beam {beam_num}', fontsize=10)
        
        plt.tight_layout()
        pdf.savefig(fig, dpi=300)
        plt.close()
        print(f"  Page 1: Stokes plots added")
        
        # Page 2: Pol-degree plots in 6x6 grid
        fig = plt.figure(figsize=(36, 36), dpi=300)
        fig.suptitle(f'Polarization Degree - All Beams{title_suffix}', fontsize=20, y=0.995)
        
        for i, img_file in enumerate(poldeg_files[:36]):  # Max 36 beams
            ax = fig.add_subplot(6, 6, i+1)
            img = mpimg.imread(img_file)
            ax.imshow(img, interpolation='none', resample=False)
            ax.axis('off')
            
            # Extract beam number from filename
            beam_num = get_beam_num(img_file)
            ax.set_title(f'Beam {beam_num}', fontsize=10)
        
        plt.tight_layout()
        pdf.savefig(fig, dpi=300)
        plt.close()
        print(f"  Page 2: Pol-degree plots added")
    
    print(f"  PDF saved: {pdf_name}")
    return pdf_name, stokes_files, poldeg_files


def plot_leakage_stats(output_dir, variant='', output_prefix='', plot_tag_text='', field_name=''):
    """
    Extract leakage statistics from text files and create a line plot.
    
    Args:
        output_dir: Directory containing the text files
        variant: '' for regular, '.lcal' for leakage calibrated
    
    Returns:
        Plot filename
    """
    # Find all text files for this variant
    if variant:
        txt_pattern = os.path.join(output_dir, f"*beam??{variant}.txt")
        plot_name = make_output_path(output_dir, output_prefix, f"leakage_stats{variant}", ".png")
        title_suffix = " (Leakage Calibrated)"
    else:
        txt_pattern = os.path.join(output_dir, "*beam??.txt")
        plot_name = make_output_path(output_dir, output_prefix, "leakage_stats", ".png")
        title_suffix = ""
    
    txt_files = sorted(glob.glob(txt_pattern))
    
    # Filter out .lcal files if we're looking for regular files
    if not variant:
        txt_files = [f for f in txt_files if '.lcal' not in f]
    
    print(f"\nProcessing leakage statistics for {variant if variant else 'regular'} variant:")
    print(f"  Found {len(txt_files)} text files")
    
    if len(txt_files) == 0:
        print(f"  WARNING: No text files found for variant '{variant}', skipping...")
        return None
    
    # Parse statistics
    beam_nums = []
    q_vals = []
    u_vals = []
    l_vals = []
    v_vals = []
    
    for txt_file in txt_files:
        # Extract beam number
        match = re.search(r'beam(\d+)', txt_file)
        if not match:
            continue
        beam_num = int(match.group(1))
        
        # Parse statistics
        stats = parse_leakage_stats(txt_file)
        if stats is None:
            print(f"  WARNING: Could not parse statistics from {os.path.basename(txt_file)}")
            continue
        
        beam_nums.append(beam_num)
        q_vals.append(stats['Q/I'])
        u_vals.append(stats['U/I'])
        l_vals.append(stats['L/I'])
        v_vals.append(stats['V/I'])
    
    if len(beam_nums) == 0:
        print(f"  ERROR: No valid statistics found")
        return None
    
    # Sort by beam number
    sorted_indices = np.argsort(beam_nums)
    beam_nums = np.array(beam_nums)[sorted_indices]
    q_vals = np.array(q_vals)[sorted_indices]
    u_vals = np.array(u_vals)[sorted_indices]
    l_vals = np.array(l_vals)[sorted_indices]
    v_vals = np.array(v_vals)[sorted_indices]
    
    # Create plot
    fig, ax = plt.subplots(1, 1, figsize=(12, 6))
    
    ax.plot(beam_nums, q_vals, 'o-', label='|Q|/I', color='red', linewidth=2, markersize=6)
    ax.plot(beam_nums, u_vals, 's-', label='|U|/I', color='blue', linewidth=2, markersize=6)
    ax.plot(beam_nums, l_vals, '^-', label='√(Q²+U²)/I', color='purple', linewidth=2.5, markersize=7)
    ax.plot(beam_nums, v_vals, 'd-', label='|V|/I', color='green', linewidth=2, markersize=6)
    
    ax.set_xlabel('Beam Number', fontsize=14)
    ax.set_ylabel('Polarization Leakage (%)', fontsize=14)
    fig.suptitle(f'Leakage Statistics vs Beam{title_suffix}', fontsize=16, fontweight='bold', y=0.985)

    if plot_tag_text:
        parts = [part.strip() for part in plot_tag_text.split(',') if part.strip()]
        tag_text = "   |   ".join(parts)
        fig.text(
            0.5,
            0.905,
            tag_text,
            ha='center',
            va='center',
            fontsize=9.5,
            color='midnightblue',
            bbox=dict(boxstyle='round,pad=0.22', facecolor='lavender', edgecolor='slateblue', alpha=0.92)
        )

    field_name_text = str(field_name or '').strip()
    if field_name_text:
        fig.text(
            0.5,
            0.865,
            f"SB_REF FIELD_NAME: {field_name_text}",
            ha='center',
            va='center',
            fontsize=9.2,
            color='darkgreen',
            bbox=dict(boxstyle='round,pad=0.20', facecolor='honeydew', edgecolor='seagreen', alpha=0.90)
        )
    else:
        fig.text(0.5, 0.865, ' ', ha='center', va='center', fontsize=9.2)
    ax.grid(True, alpha=0.3)
    ax.legend(loc='best', fontsize=12)
    ax.set_xticks(beam_nums)
    
    plt.tight_layout(rect=[0, 0, 1, 0.83])
    plt.savefig(plot_name, dpi=150, bbox_inches='tight')
    plt.close()
    
    print(f"  Plot saved: {plot_name}")
    print(f"  Statistics for {len(beam_nums)} beams:")
    print(f"    |Q|/I: {np.mean(q_vals):.3f}% ± {np.std(q_vals):.3f}%")
    print(f"    |U|/I: {np.mean(u_vals):.3f}% ± {np.std(u_vals):.3f}%")
    print(f"    √(Q²+U²)/I: {np.mean(l_vals):.3f}% ± {np.std(l_vals):.3f}%")
    print(f"    |V|/I: {np.mean(v_vals):.3f}% ± {np.std(v_vals):.3f}%")
    
    return plot_name


def create_movie(image_files, output_name, title):
    """
    Create both MP4 and GIF animations from a sequence of images.
    
    Args:
        image_files: List of image filenames (sorted by beam number)
        output_name: Output MP4 filename (GIF will have same base name)
        title: Title for the movie frames
    """
    if len(image_files) == 0:
        print(f"  WARNING: No images to create movie")
        return None
    
    print(f"\n  Creating animations from {len(image_files)} frames...")
    
    results = []
    
    # 1. Create MP4 using ffmpeg
    ffmpeg_path = "/opt/homebrew/bin/ffmpeg"
    
    if os.path.exists(ffmpeg_path):
        print(f"  Creating MP4: {output_name}")
        
        # Create a temporary file list for ffmpeg
        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            filelist_path = f.name
            for img_file in image_files:
                # ffmpeg concat requires format: file 'path'
                # duration 1 = 1 second per frame
                f.write(f"file '{os.path.abspath(img_file)}'\n")
                f.write(f"duration 1\n")
            # Add last file again without duration for proper ending
            f.write(f"file '{os.path.abspath(image_files[-1])}'\n")
        
        try:
            import subprocess
            
            # Build ffmpeg command
            cmd = [
                ffmpeg_path,
                '-f', 'concat',
                '-safe', '0',
                '-i', filelist_path,
                '-vf', 'scale=trunc(iw/2)*2:trunc(ih/2)*2',  # Ensure even dimensions
                '-c:v', 'libx264',
                '-pix_fmt', 'yuv420p',
                '-y',
                output_name
            ]
            
            result = subprocess.run(cmd, check=True, capture_output=True, text=True)
            print(f"    MP4 saved: {output_name}")
            results.append(output_name)
            
        except subprocess.CalledProcessError as e:
            print(f"    ERROR creating MP4: {e}")
            print(f"    stderr: {e.stderr}")
        except Exception as e:
            print(f"    ERROR: {e}")
        finally:
            if os.path.exists(filelist_path):
                os.unlink(filelist_path)
    else:
        print(f"  WARNING: ffmpeg not found at {ffmpeg_path}, skipping MP4")
    
    # 2. Create GIF using ImageMagick convert
    convert_path = "/opt/homebrew/bin/convert"
    gif_name = output_name.replace('.mp4', '.gif')
    
    if os.path.exists(convert_path):
        print(f"  Creating GIF: {gif_name}")
        
        try:
            import subprocess
            
            # Build convert command
            # -delay 100 = 100/100 = 1 second per frame
            # -loop 0 = loop forever
            cmd = [convert_path, "-delay", "100", "-loop", "0"]
            cmd.extend(image_files)
            cmd.append(gif_name)
            
            result = subprocess.run(cmd, check=True, capture_output=True, text=True)
            print(f"    GIF saved: {gif_name}")
            results.append(gif_name)
            
        except subprocess.CalledProcessError as e:
            print(f"    ERROR creating GIF: {e}")
            print(f"    stderr: {e.stderr}")
        except Exception as e:
            print(f"    ERROR: {e}")
    else:
        print(f"  WARNING: convert not found at {convert_path}, skipping GIF")
    
    return results if results else None


def main():
    args = parse_args()
    output_dir = args.output_directory
    
    if not os.path.isdir(output_dir):
        print(f"ERROR: {output_dir} is not a valid directory")
        sys.exit(1)
    
    print("="*60)
    print("COMBINING BEAM OUTPUTS")
    print("="*60)
    print(f"Output directory: {output_dir}")

    name_tokens = derive_name_tokens(output_dir)
    sb_ref, sb_1934, sb_holo, sb_target = resolve_plot_tags(name_tokens, args)
    plot_tag_text = f"{sb_ref}, {sb_1934}, {sb_holo}, {sb_target}"
    field_name = (args.field_name or '').strip()

    output_prefix = build_output_prefix(
        output_dir,
        explicit_prefix=args.output_prefix,
        template=args.name_template,
        max_len=args.max_prefix_len,
        legacy_names=args.legacy_names,
        extra_tags=build_optional_param_tags(args),
    )
    if output_prefix:
        print(f"Output prefix: {output_prefix}")
    else:
        print("Output prefix: <legacy names>")

    if args.dry_run:
        ffmpeg_path = "/opt/homebrew/bin/ffmpeg"
        convert_path = "/opt/homebrew/bin/convert"
        has_ffmpeg = os.path.exists(ffmpeg_path)
        has_convert = os.path.exists(convert_path)

        print("\n" + "="*60)
        print("DRY RUN: PLANNED OUTPUTS")
        print("="*60)

        for variant, label in [('', 'REGULAR'), ('.lcal', 'LEAKAGE CALIBRATED')]:
            stokes_files, poldeg_files, txt_files = summarize_variant_inputs(output_dir, variant)
            has_plot_inputs = len(stokes_files) > 0 and len(poldeg_files) > 0
            has_txt_inputs = len(txt_files) > 0

            print(f"\n[{label}] input counts: stokes={len(stokes_files)}, pol-degree={len(poldeg_files)}, txt={len(txt_files)}")

            pdf_stem = f"combined_beams{variant}" if variant else "combined_beams"
            leakage_stem = f"leakage_stats{variant}" if variant else "leakage_stats"
            stokes_movie_stem = f"beams_stokes{variant}" if variant else "beams_stokes"
            poldeg_movie_stem = f"beams_pol-degree{variant}" if variant else "beams_pol-degree"

            planned_pdf = make_output_path(output_dir, output_prefix, pdf_stem, ".pdf")
            planned_leakage = make_output_path(output_dir, output_prefix, leakage_stem, ".png")
            planned_stokes_mp4 = make_output_path(output_dir, output_prefix, stokes_movie_stem, ".mp4")
            planned_poldeg_mp4 = make_output_path(output_dir, output_prefix, poldeg_movie_stem, ".mp4")
            planned_stokes_gif = planned_stokes_mp4.replace('.mp4', '.gif')
            planned_poldeg_gif = planned_poldeg_mp4.replace('.mp4', '.gif')

            if has_plot_inputs:
                print(f"  WOULD WRITE: {planned_pdf}")
                if has_ffmpeg:
                    print(f"  WOULD WRITE: {planned_stokes_mp4}")
                    print(f"  WOULD WRITE: {planned_poldeg_mp4}")
                else:
                    print(f"  SKIP MP4 (ffmpeg not found at {ffmpeg_path})")

                if has_convert:
                    print(f"  WOULD WRITE: {planned_stokes_gif}")
                    print(f"  WOULD WRITE: {planned_poldeg_gif}")
                else:
                    print(f"  SKIP GIF (convert not found at {convert_path})")
            else:
                print("  SKIP PDF/Movies (missing required stokes and/or pol-degree inputs)")

            if has_txt_inputs:
                print(f"  WOULD WRITE: {planned_leakage}")
            else:
                print("  SKIP leakage stats plot (no matching text inputs)")

        print("\nNo files were written (dry-run mode).")
        sys.exit(0)
    
    # Process regular variant
    print("\n" + "="*60)
    print("REGULAR VARIANT")
    print("="*60)
    result = create_combined_pdf(output_dir, variant='', output_prefix=output_prefix)
    if result:
        pdf_name, stokes_files, poldeg_files = result
        # Create movies
        stokes_movie = make_output_path(output_dir, output_prefix, "beams_stokes", ".mp4")
        poldeg_movie = make_output_path(output_dir, output_prefix, "beams_pol-degree", ".mp4")
        create_movie(stokes_files, stokes_movie, "Stokes Parameters")
        create_movie(poldeg_files, poldeg_movie, "Polarization Degree")
    plot_leakage_stats(output_dir, variant='', output_prefix=output_prefix, plot_tag_text=plot_tag_text, field_name=field_name)
    
    # Process .lcal variant
    print("\n" + "="*60)
    print("LEAKAGE CALIBRATED VARIANT")
    print("="*60)
    result = create_combined_pdf(output_dir, variant='.lcal', output_prefix=output_prefix)
    if result:
        pdf_name, stokes_files, poldeg_files = result
        # Create movies
        stokes_movie = make_output_path(output_dir, output_prefix, "beams_stokes.lcal", ".mp4")
        poldeg_movie = make_output_path(output_dir, output_prefix, "beams_pol-degree.lcal", ".mp4")
        create_movie(stokes_files, stokes_movie, "Stokes Parameters (Leakage Calibrated)")
        create_movie(poldeg_files, poldeg_movie, "Polarization Degree (Leakage Calibrated)")
    plot_leakage_stats(output_dir, variant='.lcal', output_prefix=output_prefix, plot_tag_text=plot_tag_text, field_name=field_name)
    
    print("\n" + "="*60)
    print("COMPLETE")
    print("="*60)


if __name__ == '__main__':
    main()
