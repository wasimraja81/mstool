#!/usr/bin/env python3
"""
plot_paf_beam_overlay.py

Overlay closepack36 beam positions on the MkII ASKAP PAF element diagram.

The 112-element MkII PAF layout is drawn entirely from code (paf_port_layout.py).
Beam positions are placed using a compass-based sky→PAF transform that correctly
accounts for pol_axis, rear-view mirroring, and focal-plane inversion.
pol_axis and centre frequency are auto-read from the schedblock metadata file.

Usage:
  python plot_paf_beam_overlay.py \\
      --footprint footprintOutput-sb81084-REF_0324-28.txt \\
      --schedblock schedblock-info-81084.txt \\
      --output paf_overlay.png

  # Show diagnostic sky-direction stars:
  python plot_paf_beam_overlay.py ... --sky-markers
"""

import argparse
import re
import sys
from pathlib import Path

import numpy as np
import matplotlib as mpl
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.patheffects as mpe
from typing import Optional

# Import the correct 112-element 12×12 PAF layout from paf_port_layout
sys.path.insert(0, str(Path(__file__).parent))
from paf_port_layout import build_port_table, draw_paf_elements, sky_to_paf_grid

# ─────────────────────────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────────────────────────

# Default PAF element pitch in degrees (sky angle per element spacing at
# ASKAP focal plane). ASKAP 12m dish, focal length ≈ 7.41m (f/0.62).
# Plate scale = f × (π/180) = 7410 × 0.01745 ≈ 129.3 mm/deg.
# MkII element pitch ≈ 87.5 mm → 87.5/129.3 ≈ 0.677°/element.
# This ratio, pitch/elem_pitch, is the "scale" used below.
DEFAULT_ELEM_PITCH_DEG = 0.677

# ASKAP dish diameter [m] — used for 1.02 λ/D beam FWHM calculation.
ASKAP_DISH_DIAM_M = 12.0

# Fallback beam circle radius in element-spacing units (used only when no
# frequency information is available).  When a centre frequency can be read
# from the schedblock the radius is computed as (1.02 λ/D / 2) / elem_pitch.
BEAM_RADIUS_ELEM = 0.8

# ─────────────────────────────────────────────────────────────────────────────
# I/O helpers
# ─────────────────────────────────────────────────────────────────────────────

def read_footprint_output(path: str) -> dict:
    """
    Parse footprintOutput text file.

    Format per line:
        <beam_id>  (<dRA_deg> <dDec_deg>)  HH:MM:SS.ss,±DD:MM:SS.ss

    Returns
    -------
    dict {int beam_id: (float dRA_deg, float dDec_deg)}
    """
    beams = {}
    pattern = re.compile(r"^\s*(\d+)\s+\(\s*([-\d.]+)\s+([-\d.]+)\)")
    for line in Path(path).read_text().splitlines():
        m = pattern.match(line)
        if m:
            bid = int(m.group(1))
            beams[bid] = (float(m.group(2)), float(m.group(3)))
    return beams


def read_schedblock_param(path: str, key: str) -> Optional[str]:
    """Return the value string for `key = value` in a schedblock-info file."""
    for line in Path(path).read_text().splitlines():
        m = re.match(rf"^{re.escape(key)}\s*=\s*(.+)$", line.strip())
        if m:
            return m.group(1).strip()
    return None


def read_pol_axis_from_schedblock(path: str) -> Optional[float]:
    """
    Read pol_axis angle from a schedblock-info file.

    The value is stored as e.g.:
        common.target.src1.pol_axis = [pa_fixed, -45.0]

    Tries src1 first, then the template key src%d.  Returns the float angle
    or None if not found.
    """
    for key in ("common.target.src1.pol_axis",
                "common.target.src%d.pol_axis"):
        raw = read_schedblock_param(path, key)
        if raw is not None:
            # format: [pa_fixed, -45.0]  or just a plain number
            m = re.search(r"[-+]?\d+(?:\.\d+)?", raw.split(",")[-1])
            if m:
                return float(m.group())
    return None


def read_centre_freq_from_schedblock(path: str) -> Optional[float]:
    """
    Read the centre frequency (MHz) from a schedblock-info file.

    Tries ``weights.centre_frequency`` first (the band-average used for
    weighting), then ``common.target.src%d.sky_frequency`` and the src1
    variant.  Returns a float (MHz) or None if not found.
    """
    for key in ("weights.centre_frequency",
                "common.target.src1.sky_frequency",
                "common.target.src%d.sky_frequency"):
        raw = read_schedblock_param(path, key)
        if raw is not None:
            try:
                return float(raw.strip())
            except ValueError:
                continue
    return None


def beam_radius_from_freq(
    freq_mhz: float,
    elem_pitch_deg: float = DEFAULT_ELEM_PITCH_DEG,
    dish_diam_m: float = ASKAP_DISH_DIAM_M,
) -> float:
    """
    Return beam circle half-width in element-spacing units.

    Uses the uniformly-illuminated circular-aperture FWHM:
        θ_FWHM = 1.02 λ / D
    so radius = θ_FWHM / 2 / elem_pitch_deg.
    """
    import math
    lam_m   = 3e8 / (freq_mhz * 1e6)
    fwhm_deg = math.degrees(1.02 * lam_m / dish_diam_m)
    return (fwhm_deg / 2.0) / elem_pitch_deg


def read_sbid_from_schedblock(path: str) -> tuple:
    """
    Read the SBID and alias from the schedblock-info file header.

    The first non-comment, non-column-header line has the format:
        81084 REF_0324-28  PROCESSING  ...

    Returns (sbid_str, alias_str) or ('unknown', '') if not found.
    """
    for line in Path(path).read_text().splitlines():
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        if re.match(r'^id\b', line, re.IGNORECASE):  # skip column-header line
            continue
        parts = line.split()
        if len(parts) >= 2 and parts[0].isdigit():
            return parts[0], parts[1]
    return 'unknown', ''


# ─────────────────────────────────────────────────────────────────────────────
# Coordinate transform
# ─────────────────────────────────────────────────────────────────────────────

def sky_to_paf(
    beams: dict,
    pitch_deg: float,
    elem_pitch_deg: float = DEFAULT_ELEM_PITCH_DEG,
    pol_axis_deg: float = 0.0,
) -> dict:
    """
    Thin wrapper — delegates to the canonical sky_to_paf_grid() in
    paf_port_layout.py.  Do NOT copy the transform logic here.
    """
    return sky_to_paf_grid(beams, pitch_deg, elem_pitch_deg, pol_axis_deg)


# ─────────────────────────────────────────────────────────────────────────────
# Main plot
# ─────────────────────────────────────────────────────────────────────────────

_PAF_LIM = 9.0   # axis half-extent in element spacings


def plot_overlay(
    beams_paf: dict,
    beam_radius: float = BEAM_RADIUS_ELEM,
    output_path: str = "paf_beam_overlay.png",
    title: str = "closepack36 beams on MkII PAF (rear view)",
    annotate_beams: bool = True,
    show_sky_markers: bool = False,
) -> None:
    fig, ax = plt.subplots(figsize=(12, 10), facecolor="white")

    # ── PAF element layout (112-element 12×12 symmetric grid) ─────────────────
    _port_table, _unused = build_port_table()
    draw_paf_elements(ax, _port_table, _unused, show_port_numbers=True)

    # ── beam circles ─────────────────────────────────────────────────────────
    beam_colour = '#888888'
    beam_ids = sorted(beams_paf.keys())

    for bid in beam_ids:
        u, v = beams_paf[bid]
        # filled circle (10% alpha) + crisp edge-only circle (95% alpha)
        ax.add_patch(mpatches.Circle((u, v), radius=beam_radius,
            facecolor=(*mpl.colors.to_rgb(beam_colour), 0.10),
            edgecolor='none', linewidth=0, zorder=3))
        ax.add_patch(mpatches.Circle((u, v), radius=beam_radius,
            facecolor='none', edgecolor=beam_colour,
            linewidth=0.7, zorder=4))

        if annotate_beams:
            ax.text(u, v, str(bid), ha='center', va='center',
                    fontsize=6.5, fontweight='bold', color='black', zorder=5,
                    path_effects=[mpe.withStroke(linewidth=2.0, foreground='white')])

    # ── shared direction vectors (used by compass and optional sky markers) ────
    _pol_axis_c  = getattr(plot_overlay, '_pol_axis',   0.0)
    _elem_pitch_c = getattr(plot_overlay, '_elem_pitch', DEFAULT_ELEM_PITCH_DEG)
    _pitch_c     = getattr(plot_overlay, '_pitch',      0.9)
    _na  = np.radians(+45.0 - _pol_axis_c)
    _nd  = np.array([np.cos(_na),  np.sin(_na)])   # sky-North direction in sky-view (N up)
    _ed  = np.array([_nd[1], -_nd[0]])             # sky-East  = 90° CW from North

    # ── compass rose (always shown) ───────────────────────────────────────────
    from matplotlib.patches import Polygon as _MplPolygon
    _lim_c = _PAF_LIM
    _org   = np.array([-0.78 * _lim_c, 0.78 * _lim_c])
    _alen  = 1.10   # needle half-length (element spacings)
    _wid   = 0.16   # diamond half-width

    def _compass_needle(centre, tip_vec, half_width):
        """Diamond needle: fills from slightly behind centre to tip."""
        perp = np.array([-tip_vec[1], tip_vec[0]])
        norm = np.linalg.norm(perp)
        if norm > 1e-9:
            perp /= norm
        tail = centre - tip_vec * 0.18
        return np.array([
            centre + tip_vec,
            centre + perp * half_width,
            tail,
            centre - perp * half_width,
        ])

    # N needle – red; S needle – white; E needle – steel blue; W needle – white
    _needles = [
        ( _alen * _nd,  'red',       'darkred',  'N', 'darkred'),
        (-_alen * _nd,  'white',     '0.45',     'S', '0.45'  ),
        ( _alen * _ed,  'steelblue', 'navy',     'E', 'navy'  ),
        (-_alen * _ed,  'white',     '0.45',     'W', '0.45'  ),
    ]
    for _tip, _fc, _ec, _lbl, _lc in _needles:
        ax.add_patch(_MplPolygon(
            _compass_needle(_org, _tip, _wid),
            closed=True, facecolor=_fc, edgecolor=_ec, linewidth=0.8, zorder=8,
        ))
        _lpos = _org + (_alen + 0.38) * (_tip / _alen)
        ax.text(*_lpos, _lbl, color=_lc, fontsize=8.5, fontweight='bold',
                ha='center', va='center', zorder=9)

    # Centre pivot dot
    ax.plot(*_org, 'o', ms=4.5, color='0.2', markeredgewidth=0, zorder=9)
    ax.text(_org[0], _org[1] - _alen - 0.75,
            f'pol_axis={_pol_axis_c:+.0f}°',
            color='0.35', fontsize=6, ha='center', va='top',
            style='italic', zorder=8)

    # ── sky-direction diagnostic markers (--sky-markers only) ────────────────
    if show_sky_markers:
        # Red star at boresight
        ax.plot(0, 0, marker='*', markersize=18, color='red',
                markeredgecolor='darkred', markeredgewidth=0.8, zorder=6)
        ax.text(0.25, 0.15, 'pointing', fontsize=5.5, color='darkred',
                fontweight='bold', ha='left', va='bottom', zorder=6)
        _dist = 3.0 * (_pitch_c / _elem_pitch_c)
        # Gold star: sky-North source → appears toward North (up) in sky-view
        u_s, v_s = _dist * _nd
        ax.plot(u_s, v_s, marker='*', markersize=18, color='gold',
                markeredgecolor='darkorange', markeredgewidth=1.0, zorder=6)
        ax.text(u_s + 0.25, v_s, 'N sky\nsource', fontsize=5.5,
                color='darkorange', fontweight='bold', ha='left', va='center', zorder=6)
        # Cyan star: sky-East source → appears toward East (right) in sky-view
        u_w, v_w = _dist * _ed
        ax.plot(u_w, v_w, marker='*', markersize=18, color='cyan',
                markeredgecolor='teal', markeredgewidth=1.0, zorder=6)
        ax.text(u_w + 0.25, v_w, 'E sky\nsource', fontsize=5.5,
                color='teal', fontweight='bold', ha='left', va='center', zorder=6)

    # ── frame ─────────────────────────────────────────────────────────────────
    ax.set_xlim(-_PAF_LIM, _PAF_LIM)
    ax.set_ylim(-_PAF_LIM, _PAF_LIM)

    ax.set_aspect("equal")
    ax.set_xlabel("PAF u  (element spacings, sky-view  ← W / E →)", fontsize=9)
    ax.set_ylabel("PAF v  (element spacings, sky-view  ↓ S / N ↑)", fontsize=9)
    ax.set_title(title, fontsize=10)
    ax.grid(True, lw=0.25, alpha=0.35, color="0.5")
    ax.tick_params(labelsize=8)

    # ── parameter annotation ──────────────────────────────────────────────────
    n_beams = len(beams_paf)
    param_txt = (
        f"beams: {n_beams}  |  "
        f"pol_axis={getattr(plot_overlay, '_pol_axis', '?')}°  "
        f"elem_pitch={getattr(plot_overlay, '_elem_pitch', '?')}°"
    )
    ax.annotate(
        param_txt,
        xy=(0.01, 0.01), xycoords="axes fraction",
        fontsize=6, color="0.4",
        bbox=dict(boxstyle="square,pad=0.2", fc="white", ec="none", alpha=0.7),
    )

    fig.tight_layout()
    fig.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved → {output_path}")


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────

def parse_args():
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument("--footprint",  required=True,
                    help="footprintOutput text file (beam sky offsets)")
    ap.add_argument("--schedblock", required=True,
                    help="schedblock-info text file")

    # Transform parameters
    grp3 = ap.add_argument_group("Transform parameters  (iterate to calibrate)")
    grp3.add_argument("--elem-pitch", type=float, default=DEFAULT_ELEM_PITCH_DEG,
                      metavar="DEG",
                      help=f"PAF element pitch in degrees (default {DEFAULT_ELEM_PITCH_DEG}°; "
                           "affects scale of beam circles on element grid)")
    grp3.add_argument("--pol-axis", type=float, default=None,
                      metavar="DEG",
                      help="Feed rotator angle in degrees; overrides value read from "
                           "schedblock. pol_axis=0 → Leg4 points North (Reynolds convention)")
    grp3.add_argument("--freq-mhz", type=float, default=None,
                      metavar="MHz",
                      help="Centre frequency (MHz); overrides value read from schedblock. "
                           "Used to compute beam FWHM = 1.02 λ/D.")
    grp3.add_argument("--dish-diam", type=float, default=ASKAP_DISH_DIAM_M,
                      metavar="M",
                      help=f"Dish diameter in metres (default {ASKAP_DISH_DIAM_M} m)")

    # Output
    ap.add_argument("--output", default="paf_beam_overlay.png",
                    help="Output PNG path (default paf_beam_overlay.png)")
    ap.add_argument("--no-labels", dest="annotate", action="store_false", default=True,
                    help="Suppress beam number labels")
    ap.add_argument("--sky-markers", dest="sky_markers", action="store_true", default=False,
                    help="Show diagnostic sky-direction markers: pointing star, "
                         "S/W sky-source stars, and N/E compass rose (off by default)")
    ap.add_argument("--beam-radius", type=float, default=None,
                    help="Beam circle radius in element units; overrides frequency-derived "
                         f"calculation (fallback default {BEAM_RADIUS_ELEM} when no freq available)")
    return ap.parse_args()


def main():
    args = parse_args()

    # ── read inputs ───────────────────────────────────────────────────────────
    beams = read_footprint_output(args.footprint)
    if not beams:
        sys.exit(f"ERROR: No beam entries found in {args.footprint!r}")

    pitch_str = read_schedblock_param(
        args.schedblock, "common.target.src%d.footprint.pitch"
    )
    rot_str = read_schedblock_param(
        args.schedblock, "weights.footprint_rotation"
    )
    if pitch_str is None or rot_str is None:
        sys.exit("ERROR: Could not read pitch or rotation from schedblock file")

    pitch = float(pitch_str)
    rotation = float(rot_str)

    # ── resolve pol_axis: CLI wins, otherwise read from schedblock ────────────
    if args.pol_axis is not None:
        pol_axis = args.pol_axis
        pol_axis_src = "CLI"
    else:
        pol_axis = read_pol_axis_from_schedblock(args.schedblock)
        if pol_axis is None:
            print("WARNING: pol_axis not found in schedblock; defaulting to 0.0")
            pol_axis = 0.0
            pol_axis_src = "default"
        else:
            pol_axis_src = "schedblock"

    # ── resolve centre frequency and beam radius ──────────────────────────────
    if args.freq_mhz is not None:
        freq_mhz   = args.freq_mhz
        freq_src   = "CLI"
    else:
        freq_mhz   = read_centre_freq_from_schedblock(args.schedblock)
        freq_src   = "schedblock" if freq_mhz is not None else None

    if args.beam_radius is not None:
        # Explicit override from --beam-radius
        beam_radius    = args.beam_radius
        beam_radius_src = "CLI (--beam-radius)"
    elif freq_mhz is not None:
        beam_radius    = beam_radius_from_freq(freq_mhz, args.elem_pitch, args.dish_diam)
        import math
        lam_m          = 3e8 / (freq_mhz * 1e6)
        fwhm_deg       = math.degrees(1.02 * lam_m / args.dish_diam)
        beam_radius_src = (f"1.02 λ/D @ {freq_mhz:.1f} MHz ({freq_src}) → "
                           f"FWHM={fwhm_deg:.3f}° → radius={beam_radius:.3f} elem")
    else:
        beam_radius    = BEAM_RADIUS_ELEM
        beam_radius_src = f"fallback default ({BEAM_RADIUS_ELEM} elem)"

    print(
        f"pitch={pitch}°  rotation={rotation}°  "
        f"elem_pitch={args.elem_pitch}°  scale={pitch/args.elem_pitch:.3f} elem/beam"
    )
    print(f"Transform: pol_axis={pol_axis:+.1f}°  (source: {pol_axis_src}, sky-view: N up, E right)")
    print(f"Beam radius: {beam_radius_src}")

    # ── transform ─────────────────────────────────────────────────────────────
    beams_paf = sky_to_paf(
        beams,
        pitch_deg      = pitch,
        elem_pitch_deg = args.elem_pitch,
        pol_axis_deg   = pol_axis,
    )

    print("Beam PAF positions (first 6):")
    for bid in sorted(beams_paf)[:6]:
        print(f"  beam {bid:2d}: ({beams_paf[bid][0]:+.3f}, {beams_paf[bid][1]:+.3f})")

    # ── stash params for annotation ───────────────────────────────────────────
    plot_overlay._pol_axis  = pol_axis
    plot_overlay._elem_pitch = args.elem_pitch
    plot_overlay._pitch     = pitch

    # ── title ─────────────────────────────────────────────────────────────────
    sbid, alias = read_sbid_from_schedblock(args.schedblock)
    pol_axis_src_label = f"pol_axis={pol_axis:+.0f}° ({pol_axis_src})"
    title = (
        f"closepack36 beams on MkII PAF (rear view) — "
        f"SB{sbid} ({alias})   {pol_axis_src_label}"
    )

    # ── plot ──────────────────────────────────────────────────────────────────
    plot_overlay(
        beams_paf,
        beam_radius      = beam_radius,
        output_path      = args.output,
        title            = title,
        annotate_beams   = args.annotate,
        show_sky_markers = args.sky_markers,
    )


if __name__ == "__main__":
    main()
