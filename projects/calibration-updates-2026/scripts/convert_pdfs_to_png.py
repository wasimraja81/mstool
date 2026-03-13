#!/usr/bin/env python3
"""Convert combined_beams PDF files in the phase3 media directory to PNGs.

Each PDF has exactly 2 pages.  Output files are written alongside the PDF:
    {stem}_p01.png
    {stem}_p02.png

Usage
-----
    python convert_pdfs_to_png.py [--media-dir DIR] [--dpi N] [--workers N] [--force]

Defaults:
    media-dir : /Users/raj030/DATA/reffield-average/phase3/media
    dpi       : 150   (5400×5400 px per page for a 36"×36" PDF)
    workers   : 4     (parallel gs processes)
    force     : False (skip already-converted PDFs)

Requirements: ghostscript (gs) must be on PATH.
"""

import argparse
import multiprocessing
import os
import pathlib
import shutil
import subprocess
import sys
from typing import Optional


# ── helpers ──────────────────────────────────────────────────────────────────

def gs_available() -> bool:
    return shutil.which("gs") is not None


def convert_one(args_tuple) -> tuple[str, Optional[str]]:
    """Worker function: convert a single PDF to per-page PNGs.

    Returns (pdf_path_str, error_message_or_None).
    """
    pdf_path_str, dpi, force = args_tuple
    pdf = pathlib.Path(pdf_path_str)
    stem = pdf.stem          # filename without .pdf
    out_dir = pdf.parent

    # Check if already done (both _p01 and _p02 exist)
    p01 = out_dir / f"{stem}_p01.png"
    p02 = out_dir / f"{stem}_p02.png"
    if not force and p01.exists() and p02.exists():
        return (pdf_path_str, None)   # skip

    out_pattern = str(out_dir / f"{stem}_p%02d.png")
    cmd = [
        "gs",
        "-dBATCH", "-dNOPAUSE", "-dQUIET",
        "-sDEVICE=png16m",
        f"-r{dpi}",
        "-dTextAlphaBits=4",
        "-dGraphicsAlphaBits=4",
        f"-sOutputFile={out_pattern}",
        str(pdf),
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
        if result.returncode != 0:
            return (pdf_path_str, result.stderr.strip()[:300])
        return (pdf_path_str, None)
    except subprocess.TimeoutExpired:
        return (pdf_path_str, "TIMEOUT after 600s")
    except Exception as exc:
        return (pdf_path_str, str(exc))


# ── main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Convert phase3 PDFs to PNGs via ghostscript")
    parser.add_argument(
        "--media-dir",
        default="/Users/raj030/DATA/reffield-average/phase3/media",
        help="Root media directory containing SB_REF-*/ subdirs",
    )
    parser.add_argument("--dpi", type=int, default=150,
                        help="Rasterisation DPI (default 150 → 5400×5400 px for 36\"×36\" pages)")
    parser.add_argument("--workers", type=int, default=4,
                        help="Number of parallel gs processes")
    parser.add_argument("--force", action="store_true",
                        help="Re-convert even if output PNGs already exist")
    args = parser.parse_args()

    media_dir = pathlib.Path(args.media_dir)
    if not media_dir.exists():
        sys.exit(f"ERROR: media dir not found: {media_dir}")
    if not gs_available():
        sys.exit("ERROR: ghostscript (gs) not found on PATH")

    # Collect all combined_beams PDFs
    pdfs = sorted(media_dir.rglob("*.combined_beams*.pdf"))
    if not pdfs:
        print("No combined_beams PDF files found.")
        return

    # Filter to pending (unless --force)
    if not args.force:
        pending = []
        skipped = 0
        for pdf in pdfs:
            p01 = pdf.parent / f"{pdf.stem}_p01.png"
            p02 = pdf.parent / f"{pdf.stem}_p02.png"
            if p01.exists() and p02.exists():
                skipped += 1
            else:
                pending.append(pdf)
        if skipped:
            print(f"Skipping {skipped} already-converted PDFs  (use --force to redo)")
    else:
        pending = pdfs

    total = len(pending)
    if total == 0:
        print("All PDFs already converted. Done.")
        return

    print(f"Converting {total} PDF(s) at {args.dpi} DPI  "
          f"using {min(args.workers, total)} workers …")

    work_items = [(str(p), args.dpi, args.force) for p in pending]

    errors = []
    completed = 0
    with multiprocessing.Pool(processes=min(args.workers, total)) as pool:
        for pdf_str, err in pool.imap_unordered(convert_one, work_items):
            completed += 1
            short = pathlib.Path(pdf_str).parent.parent.name + "/" + pathlib.Path(pdf_str).name[-40:]
            if err:
                errors.append((pdf_str, err))
                print(f"  [{completed}/{total}] ERROR  …{short}")
                print(f"           {err}")
            else:
                # Report output size
                stem = pathlib.Path(pdf_str).stem
                out_dir = pathlib.Path(pdf_str).parent
                sizes = []
                for page in ("p01", "p02"):
                    f = out_dir / f"{stem}_{page}.png"
                    if f.exists():
                        sizes.append(f"{f.stat().st_size / 1024:.0f} KB")
                size_str = "  ".join(sizes)
                print(f"  [{completed}/{total}] OK     …{short[-50:]}  →  {size_str}")

    print()
    if errors:
        print(f"Finished with {len(errors)} error(s):")
        for p, e in errors:
            print(f"  {p}")
            print(f"    {e}")
        sys.exit(1)
    else:
        print(f"All {total} PDF(s) converted successfully.")


if __name__ == "__main__":
    main()
