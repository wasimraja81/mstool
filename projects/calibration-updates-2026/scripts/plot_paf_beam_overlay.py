#!/usr/bin/env python3
"""
plot_paf_beam_overlay.py

Overlay closepack36 beam positions on the MkII ASKAP PAF element diagram.

Transform chain (sky frame → PAF rear-view frame):
  1. Read beam sky offsets from footprintOutput (degrees)
  2. Divide by pitch → normalised units (1 unit = beam spacing = pitch)
  3. Rotate by -footprint.rotation (undo the sky rotation → PAF canonical frame)
  4. Scale by (pitch / element_pitch) → units of one PAF element spacing
  5. Optionally flip X (left-right) for rear-view convention
  6. Optionally flip Y (up-down) for focal-plane inversion

The sign of the rotation and both flip flags are left as tunable parameters so the
mapping can be verified empirically once an anchor referencing the physical PAF is
available (leg orientation, known bright-source position, etc.).

PAF image coordinate calibration:
  The background image is aligned by specifying the PAF coordinates
  [xmin, xmax, ymin, ymax] that correspond to the image edges via --image-extent.
  Start with --image-half-extent to set a symmetric window.

Usage examples:
  # No background image (synthetic grid only):
  python plot_paf_beam_overlay.py \\
      --footprint footprintOutput-sb81084-REF_0324-28.txt \\
      --schedblock schedblock-info-81084.txt \\
      --output paf_overlay_v0.png

  # With PAF diagram as background:
  python plot_paf_beam_overlay.py \\
      --footprint footprintOutput-sb81084-REF_0324-28.txt \\
      --schedblock schedblock-info-81084.txt \\
      --paf-image /path/to/MkII_PAF.png \\
      --image-half-extent 8.5 \\
      --flip-lr \\
      --output paf_overlay_v1.png

  # Tune rotation offset and scale:
  python plot_paf_beam_overlay.py ... --pa-offset 90 --elem-pitch 0.75
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
from matplotlib.collections import PatchCollection
from typing import Optional

# Import the correct 112-element 12×12 PAF layout from paf_port_layout
sys.path.insert(0, str(Path(__file__).parent))
from paf_port_layout import build_port_table, draw_paf_elements

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

# Leg colours matching the MkII PAF diagram quadrants
LEG_COLOUR = {
    "R": "#dd4444",   # Leg 1 – upper right  (Red region)
    "G": "#44aa44",   # Leg 2 – upper left   (Green region)
    "B": "#4466cc",   # Leg 3 – lower left   (Blue region)
    "Y": "#ccaa00",   # Leg 4 – lower right  (Yellow region)
}

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
    Project sky-frame beam offsets (x_sky=East, y_sky=North, degrees) onto
    the PAF rear-view grid using the physically-motivated compass transform.

    Physics:
      - Telescope focal-plane inverts the sky image: source at (x,y) sky
        appears at (-x,-y) on the focal plane in the sky frame.
      - pol_axis=0  →  Leg4 points North (Reynolds convention).
      - Rear view  →  East/West are mirrored vs sky; East on sky appears to
        the left (toward Leg3) in the rear-view diagram.
      - North on PAF rear-view: angle = -45° - pol_axis_deg from the +u axis.
      - East on PAF rear-view: 90° clockwise from North.

    Parameters
    ----------
    beams         : {beam_id: (x_sky, y_sky)} in degrees
    pitch_deg     : beam pitch (degrees)
    elem_pitch_deg: PAF physical element pitch in degrees
    pol_axis_deg  : feed rotator angle (degrees); 0 = Leg4 toward North

    Returns
    -------
    dict {beam_id: (u_elem, v_elem)} in units of one PAF element spacing
    """
    scale = pitch_deg / elem_pitch_deg
    na    = np.radians(-45.0 - pol_axis_deg)
    nd    = np.array([np.cos(na),  np.sin(na)])   # North unit vector
    ed    = np.array([nd[1],      -nd[0]])          # East  unit vector (90° CW in rear view)
    result = {}
    for bid, (x_sky, y_sky) in beams.items():
        u = scale / pitch_deg * (-y_sky * nd[0] - x_sky * ed[0])
        v = scale / pitch_deg * (-y_sky * nd[1] - x_sky * ed[1])
        result[bid] = (float(u), float(v))
    return result


# ─────────────────────────────────────────────────────────────────────────────
# PAF element synthetic grid
# ─────────────────────────────────────────────────────────────────────────────

def _paf_quadrant(u: float, v: float) -> str:
    """
    Assign a leg-colour key based on position in PAF rear-view frame.
    Quadrant boundaries at u=0 and v=0 match the image colour regions:
      R (red)    : u > 0 , v > 0   (upper-right → Leg 1)
      G (green)  : u < 0 , v > 0   (upper-left  → Leg 2)
      B (blue)   : u < 0 , v < 0   (lower-left  → Leg 3)
      Y (yellow) : u > 0 , v < 0   (lower-right → Leg 4)
    """
    if u >= 0 and v >= 0:
        return "R"
    if u < 0 and v >= 0:
        return "G"
    if u < 0 and v < 0:
        return "B"
    return "Y"


def build_paf_element_grid(n_max: int = 7) -> list:
    """
    Generate (i, j) integer grid positions for the MkII PAF elements in a
    diamond boundary |i| + |j| ≤ n_max.

    n_max=7 → 113 elements (slightly more than 94; use for a good visual)
    n_max=6 → 85 elements (slightly fewer than 94)
    Adjust n_max or switch to circular boundary to match exact count if needed.

    Returns list of ((i, j), colour_key).
    """
    elements = []
    for i in range(-n_max, n_max + 1):
        for j in range(-n_max, n_max + 1):
            if abs(i) + abs(j) <= n_max:
                col = _paf_quadrant(float(i), float(j))
                elements.append(((i, j), col))
    return elements


def draw_paf_grid(ax: plt.Axes, n_max: int = 7, alpha: float = 0.30) -> None:
    """
    Draw the synthetic PAF element grid on *ax*.  Each element is shown as a
    small rotated square (diamond) centred at its (i, j) grid position.

    The effective element size is 0.85 × spacing so gaps are visible.
    """
    half = 0.40   # half-size of each diamond in element units
    elements = build_paf_element_grid(n_max)

    for (i, j), ckey in elements:
        colour = LEG_COLOUR[ckey]
        # Rotated-square vertices (diamond in the plot)
        verts = np.array([
            [i + half, j],
            [i,        j + half],
            [i - half, j],
            [i,        j - half],
        ])
        poly = mpatches.Polygon(
            verts,
            closed=True,
            linewidth=0.5,
            edgecolor="0.55",
            facecolor=(*mpl.colors.to_rgb(colour), alpha),
            zorder=1,
        )
        ax.add_patch(poly)

    # Draw the leg corner markers
    span = n_max + 1.2
    for angle_deg, label, ha, va in [
        (45,  "Leg 1", "left",  "bottom"),
        (135, "Leg 2", "right", "bottom"),
        (225, "Leg 3", "right", "top"),
        (315, "Leg 4", "left",  "top"),
    ]:
        ang = np.radians(angle_deg)
        x0, y0 = 0.72 * span * np.cos(ang), 0.72 * span * np.sin(ang)
        x1, y1 = 0.95 * span * np.cos(ang), 0.95 * span * np.sin(ang)
        ax.annotate(
            "",
            xy=(x0, y0),
            xytext=(x1, y1),
            arrowprops=dict(arrowstyle="->", color="0.4", lw=1.2),
            zorder=5,
        )
        ax.text(
            1.07 * span * np.cos(ang),
            1.07 * span * np.sin(ang),
            label,
            ha=ha, va=va,
            fontsize=8, color="0.35", fontweight="bold",
        )


# ─────────────────────────────────────────────────────────────────────────────
# Main plot
# ─────────────────────────────────────────────────────────────────────────────

def plot_overlay(
    beams_paf: dict,
    paf_image_path: Optional[str] = None,
    image_extent: Optional[list] = None,  # [xmin, xmax, ymin, ymax] in elem units
    image_alpha: float = 0.65,
    grid_n_max: int = 7,
    beam_radius: float = BEAM_RADIUS_ELEM,
    output_path: str = "paf_beam_overlay.png",
    title: str = "closepack36 beams on MkII PAF (rear view)",
    annotate_beams: bool = True,
    show_sky_markers: bool = False,
) -> None:
    fig, ax = plt.subplots(figsize=(12, 10), facecolor="white")

    # ── background image ──────────────────────────────────────────────────────
    use_image = paf_image_path and Path(paf_image_path).exists()
    if use_image:
        img = mpl.image.imread(paf_image_path)
        if image_extent is None:
            image_extent = [-9, 9, -9, 9]
        ax.imshow(
            img,
            extent=image_extent,   # [left, right, bottom, top] in elem units
            origin="upper",        # image row 0 at top (standard PNG)
            aspect="equal",
            alpha=image_alpha,
            zorder=0,
        )
    else:
        # Draw the correct 112-element 12×12 symmetric PAF layout
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
    _na  = np.radians(-45.0 - _pol_axis_c)
    _nd  = np.array([np.cos(_na),  np.sin(_na)])   # North unit vector on PAF rear-view
    _ed  = np.array([_nd[1], -_nd[0]])             # East  = 90° CW from North

    # ── compass rose (always shown) ───────────────────────────────────────────
    from matplotlib.patches import Polygon as _MplPolygon
    _lim_c = grid_n_max + 2.5
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
        # Gold star: South sky source → focal plane inverts → toward North on PAF
        u_s, v_s = _dist * _nd
        ax.plot(u_s, v_s, marker='*', markersize=18, color='gold',
                markeredgecolor='darkorange', markeredgewidth=1.0, zorder=6)
        ax.text(u_s + 0.25, v_s, 'S sky\nsource', fontsize=5.5,
                color='darkorange', fontweight='bold', ha='left', va='center', zorder=6)
        # Cyan star: West sky source → appears toward East on PAF
        u_w, v_w = _dist * _ed
        ax.plot(u_w, v_w, marker='*', markersize=18, color='cyan',
                markeredgecolor='teal', markeredgewidth=1.0, zorder=6)
        ax.text(u_w + 0.25, v_w, 'W sky\nsource', fontsize=5.5,
                color='teal', fontweight='bold', ha='left', va='center', zorder=6)

    # ── frame ─────────────────────────────────────────────────────────────────
    if use_image and image_extent:
        pad = (image_extent[1] - image_extent[0]) * 0.05
        ax.set_xlim(image_extent[0] - pad, image_extent[1] + pad)
        ax.set_ylim(image_extent[2] - pad, image_extent[3] + pad)
    else:
        lim = grid_n_max + 2.5
        ax.set_xlim(-lim, lim)
        ax.set_ylim(-lim, lim)

    ax.set_aspect("equal")
    ax.set_xlabel("PAF u  (element spacings, rear-view)", fontsize=9)
    ax.set_ylabel("PAF v  (element spacings, rear-view)", fontsize=9)
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

    # Background image
    grp = ap.add_argument_group("Background image")
    grp.add_argument("--paf-image", default=None,
                     help="PAF diagram PNG/JPEG to use as background")
    grp.add_argument("--image-half-extent", type=float, default=9.0,
                     metavar="H",
                     help="Symmetric half-extent: image spans [-H,H] × [-H,H] "
                          "in element units (default 9.0; tune to fit diagram)")
    grp.add_argument("--image-extent", nargs=4, type=float,
                     metavar=("XMIN", "XMAX", "YMIN", "YMAX"),
                     help="Explicit image extent (overrides --image-half-extent)")
    grp.add_argument("--image-alpha", type=float, default=0.65,
                     help="Opacity of background image (default 0.65)")

    # Synthetic grid (used when no --paf-image)
    grp2 = ap.add_argument_group("Synthetic PAF grid (no --paf-image)")
    grp2.add_argument("--grid-n", type=int, default=7,
                      help="Diamond half-width for synthetic grid (default 7 → 113 elements)")

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
    print(f"Transform: pol_axis={pol_axis:+.1f}°  (source: {pol_axis_src}, compass-based, rear view)")
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

    # ── image extent ──────────────────────────────────────────────────────────
    if args.image_extent:
        image_extent = args.image_extent
    else:
        h = args.image_half_extent
        image_extent = [-h, h, -h, h]

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
        paf_image_path  = args.paf_image,
        image_extent    = image_extent,
        image_alpha     = args.image_alpha,
        grid_n_max      = args.grid_n,
        beam_radius     = beam_radius,
        output_path     = args.output,
        title           = title,
        annotate_beams  = args.annotate,
        show_sky_markers = args.sky_markers,
    )


if __name__ == "__main__":
    main()
