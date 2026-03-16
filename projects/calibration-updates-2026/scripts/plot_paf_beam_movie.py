#!/usr/bin/env python3
"""
plot_paf_beam_movie.py

Animate the closepack-36 beam footprint on the MkII ASKAP PAF layout.
One frame per beam; the active beam is shown as an Airy diffraction pattern
(to the 3rd null) with intensity-weighted grey tones (white=peak, black=null).
Already-visited beams accumulate as a faint trail.

Requires: ffmpeg on PATH for MP4 output.

Usage:
  python plot_paf_beam_movie.py \\
      --footprint path/to/footprintOutput-sb81084-REF_0324-28.txt \\
      --schedblock path/to/schedblock-info-81084.txt \\
      --output paf_beam_movie.mp4

  # Tunable options:
  python plot_paf_beam_movie.py ... --fps 1 --trail 0.3 --gamma 0.5 --cmap Blues
"""

import argparse
import sys
from pathlib import Path

import numpy as np
import matplotlib as mpl
mpl.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.animation as animation
import matplotlib.patches as mpatches
import matplotlib.patheffects as mpe
from matplotlib.patches import Polygon as _MplPoly

# ── Import shared helpers from plot_paf_beam_overlay ─────────────────────────
sys.path.insert(0, str(Path(__file__).parent))
from paf_port_layout import build_port_table, draw_paf_elements
from plot_paf_beam_overlay import (
    read_footprint_output,
    read_pol_axis_from_schedblock,
    read_centre_freq_from_schedblock,
    read_sbid_from_schedblock,
    sky_to_paf,
    beam_radius_from_freq,
    DEFAULT_ELEM_PITCH_DEG,
    ASKAP_DISH_DIAM_M,
    BEAM_RADIUS_ELEM,
    _PAF_LIM,
)

# ── Airy pattern ──────────────────────────────────────────────────────────────
try:
    from scipy.special import j1 as _j1
    _HAVE_SCIPY = True
except ImportError:
    _HAVE_SCIPY = False


def airy_intensity(r_norm: np.ndarray) -> np.ndarray:
    """
    Normalised Airy pattern intensity.

    Parameters
    ----------
    r_norm : array-like
        Radial coordinate normalised so that the *first null* occurs at
        r_norm = 1.  (i.e. r_norm = r_elem / r_null1_elem)

    Returns
    -------
    I : ndarray in [0, 1], same shape as r_norm.  I(0) = 1.
    """
    # Airy: I(x) = [2 J1(x) / x]^2,  first null at x = 3.8317
    x = r_norm * 3.8317
    with np.errstate(divide="ignore", invalid="ignore"):
        val = np.where(x == 0.0, 1.0, (2.0 * _j1(x) / x) ** 2)
    return np.clip(val, 0.0, 1.0)


def gaussian_intensity(r_norm: np.ndarray) -> np.ndarray:
    """Gaussian fallback when scipy is not available.  Same r_norm convention."""
    # FWHM <=> r_norm ~ 0.6 (Gaussian FWHM ≈ 0.60× first Airy null)
    sigma = 0.425
    return np.exp(-0.5 * (r_norm / sigma) ** 2)


# Null radii as multiples of the FIRST null radius (r_null1 = 1.22 λ/D)
# 2nd null ≈ 2.233 × first null, 3rd null ≈ 3.238 × first null
_AIRY_NULL_RATIO = {1: 1.0, 2: 2.233, 3: 3.238}

# Relationship: beam_radius (FWHM/2 in elem units) → first null distance
# FWHM = 1.02 λ/D  →  FWHM/2 = 0.51 λ/D
# first_null = 1.22 λ/D = (1.22/0.51) × FWHM/2 ≈ 2.392 × beam_radius_elem
_FWHM2_TO_NULL1 = 1.22 / 0.51   # = 2.392


def airy_rgba_disk(
    cx: float, cy: float,
    beam_radius_elem: float,
    n_nulls: int,
    grid_x: np.ndarray,
    grid_y: np.ndarray,
    cmap,
    gamma: float = 0.5,
) -> np.ndarray:
    """
    Return an RGBA image (same shape as grid_x/y) for one Airy beam.

    Parameters
    ----------
    cx, cy             : beam centre in PAF element coordinates
    beam_radius_elem   : FWHM/2 in element units (the overlay circle radius)
    n_nulls            : truncate Airy pattern outside the nth null
    grid_x, grid_y     : 2-D coordinate arrays over the PAF canvas
    cmap               : matplotlib colormap (e.g. Blues)
    gamma              : power-law exponent applied to intensity for display
                         (< 1 brightens mid-tones; highlights rings)
    """
    r_null1 = _FWHM2_TO_NULL1 * beam_radius_elem      # 1st null in elem units
    r_cutoff = r_null1 * _AIRY_NULL_RATIO[n_nulls]    # 3rd null for n_nulls=3

    dist = np.sqrt((grid_x - cx) ** 2 + (grid_y - cy) ** 2)
    r_norm = dist / r_null1                             # 1 at 1st null

    if _HAVE_SCIPY:
        intensity = airy_intensity(r_norm)
    else:
        intensity = gaussian_intensity(r_norm)

    # Apply power-law display gamma (enhances ring visibility)
    display = np.clip(intensity ** gamma, 0.0, 1.0)

    # Mask outside nth null
    mask = dist <= r_cutoff

    rgba = cmap(display)                               # shape (..., 4)
    rgba[..., 3] = display * mask                      # alpha = intensity × mask
    return rgba.astype(np.float32)


# ── Compass rose helper (copied from plot_paf_beam_overlay) ───────────────────
def _draw_compass(ax, nd, ed, lim=_PAF_LIM):
    """Draw a diamond-needle compass rose in the top-left corner."""
    org   = np.array([-0.78 * lim, 0.78 * lim])
    alen  = 1.10
    wid   = 0.16

    def _needle(centre, tip_vec, hw):
        perp = np.array([-tip_vec[1], tip_vec[0]])
        n = np.linalg.norm(perp)
        if n > 1e-9:
            perp /= n
        tail = centre - tip_vec * 0.18
        return np.array([centre + tip_vec, centre + perp * hw,
                         tail, centre - perp * hw])

    for tip, fc, ec, lbl, lc in [
        ( alen * nd, "red",       "darkred", "N", "darkred"),
        (-alen * nd, "white",     "0.45",    "S", "0.45"),
        ( alen * ed, "steelblue", "navy",    "E", "navy"),
        (-alen * ed, "white",     "0.45",    "W", "0.45"),
    ]:
        ax.add_patch(_MplPoly(_needle(org, tip, wid), closed=True,
                              facecolor=fc, edgecolor=ec, lw=0.8, zorder=12))
        lpos = org + (alen + 0.38) * (tip / alen)
        ax.text(*lpos, lbl, color=lc, fontsize=8.5, fontweight="bold",
                ha="center", va="center", zorder=13)


# ── Main animation builder ────────────────────────────────────────────────────

def build_movie(
    footprint_path: str,
    schedblock_path: str,
    output_path: str,
    fps: int = 2,
    n_nulls: int = 3,
    trail_alpha_scale: float = 0.22,
    gamma: float = 0.45,
    cmap_name: str = "gray",
    dpi: int = 150,
    grid_res: int = 500,
    hold_frames: int = 2,
    freq_mhz_override: float = None,
    elem_pitch_override: float = None,
    dish_diam_override: float = None,
) -> None:
    # ── Read inputs ───────────────────────────────────────────────────────────
    beams_sky = read_footprint_output(footprint_path)
    if not beams_sky:
        raise ValueError(f"No beams parsed from {footprint_path}")

    sbid, alias = read_sbid_from_schedblock(schedblock_path)

    freq_mhz = freq_mhz_override or read_centre_freq_from_schedblock(schedblock_path) or 920.5
    pol_axis = read_pol_axis_from_schedblock(schedblock_path) or 0.0
    elem_pitch = elem_pitch_override or DEFAULT_ELEM_PITCH_DEG
    dish_diam  = dish_diam_override  or ASKAP_DISH_DIAM_M

    beam_radius = beam_radius_from_freq(freq_mhz, elem_pitch, dish_diam)
    fwhm_deg    = 2 * beam_radius * elem_pitch

    # Refine pitch from footprint actual beam separations
    bvals = np.array(list(beams_sky.values()))
    dists = np.sqrt(np.diff(bvals[:, 0]) ** 2 + np.diff(bvals[:, 1]) ** 2)
    dists_pos = dists[dists > 0.01]
    pitch_deg = float(np.min(dists_pos)) if len(dists_pos) else fwhm_deg * 0.9

    print(f"SB{sbid} ({alias})  freq={freq_mhz:.1f} MHz  pol_axis={pol_axis:.1f}°")
    print(f"pitch={pitch_deg:.3f}°  elem_pitch={elem_pitch:.3f}°  beam_radius={beam_radius:.3f} elem")
    print(f"Airy 3rd null @ {beam_radius * _FWHM2_TO_NULL1 * _AIRY_NULL_RATIO[n_nulls]:.2f} elem")

    # ── Build PAF-frame beam positions ────────────────────────────────────────
    beams_paf = sky_to_paf(beams_sky, pitch_deg, elem_pitch, pol_axis)
    beam_ids  = sorted(beams_paf.keys())
    n_beams   = len(beam_ids)

    # ── North/East unit vectors in sky-view (N up, E right) ─────────────────
    na = np.radians(+45.0 - pol_axis)
    nd = np.array([np.cos(na),  np.sin(na)])   # sky-North direction
    ed = np.array([ nd[1],     -nd[0]])         # sky-East  direction

    # ── Airy grid ─────────────────────────────────────────────────────────────
    lim  = _PAF_LIM
    xs   = np.linspace(-lim, lim, grid_res)
    ys   = np.linspace(-lim, lim, grid_res)
    gx, gy = np.meshgrid(xs, ys)
    cmap = plt.get_cmap(cmap_name)

    # Pre-compute RGBA for every beam
    print("Pre-computing Airy disks … ", end="", flush=True)
    beam_rgba = {}
    for bid in beam_ids:
        cx, cy = beams_paf[bid]
        beam_rgba[bid] = airy_rgba_disk(cx, cy, beam_radius, n_nulls,
                                        gx, gy, cmap, gamma)
    print("done")

    # Cumulative trail array (RGB only; alpha managed per layer)
    trail_rgba = np.zeros((grid_res, grid_res, 4), dtype=np.float32)

    # ── Figure setup ──────────────────────────────────────────────────────────
    figsize = (10, 8.5)
    fig, ax = plt.subplots(figsize=figsize, facecolor="white")
    ax.set_facecolor("white")
    ax.set_aspect("equal")
    ax.set_xlim(-lim, lim)
    ax.set_ylim(-lim, lim)
    ax.set_xlabel("PAF u (element spacings  ← W / E →)", fontsize=9)
    ax.set_ylabel("PAF v (element spacings  ↓ S / N ↑)", fontsize=9)

    # ── Static layers ─────────────────────────────────────────────────────────
    port_table, unused_set = build_port_table()
    draw_paf_elements(ax, port_table, unused_set, show_port_numbers=True)
    _draw_compass(ax, nd, ed, lim)

    # small cross-hair at PAF centre
    ax.axhline(0, color="0.85", lw=0.5, zorder=0)
    ax.axvline(0, color="0.85", lw=0.5, zorder=0)

    # ── Dynamic layers ────────────────────────────────────────────────────────
    # imshow extent: left, right, bottom, top in data coords
    extent = (-lim, lim, -lim, lim)
    trail_im  = ax.imshow(trail_rgba,  extent=extent, origin="lower",
                          interpolation="bilinear", zorder=4, animated=True)
    current_im = ax.imshow(np.zeros((grid_res, grid_res, 4), dtype=np.float32),
                           extent=extent, origin="lower",
                           interpolation="bilinear", zorder=5, animated=True)

    # Beam-number text (top-right corner)
    beam_lbl = ax.text(0.97, 0.97, "", transform=ax.transAxes,
                       ha="right", va="top", fontsize=14, fontweight="bold",
                       color="#1a4e8a", zorder=11,
                       path_effects=[mpe.withStroke(linewidth=2.5, foreground="white")])

    # Small dot at each beam centre (always visible)
    dot_artists = {}
    for bid in beam_ids:
        cx, cy = beams_paf[bid]
        dot, = ax.plot(cx, cy, "o", ms=2.0, color="0.5",
                       alpha=0.4, zorder=6, animated=True)
        dot_artists[bid] = dot

    title_str = (
        f"PAF beam-overlay  SB{sbid} · {alias}\n"
        f"{freq_mhz:.1f} MHz   pol_axis={pol_axis:+.1f}°"
    )
    ax.set_title(title_str, fontsize=10, pad=6)

    # ── Animation frames ──────────────────────────────────────────────────────
    # Frame layout: n_beams active frames + hold_frames at end
    total_frames = n_beams + hold_frames

    def update(frame_idx):
        nonlocal trail_rgba

        if frame_idx >= n_beams:
            # Hold: just keep the final state, no change needed
            return [trail_im, current_im, beam_lbl] + list(dot_artists.values())

        bid = beam_ids[frame_idx]
        cx, cy = beams_paf[bid]

        # Current frame: full Airy disk for this beam
        cur = beam_rgba[bid].copy()
        current_im.set_data(cur)

        # Trail: blend previous beams in at reduced alpha
        # Add the *previous* frame's beam to the trail after it's been shown
        if frame_idx > 0:
            prev_bid = beam_ids[frame_idx - 1]
            prev = beam_rgba[prev_bid]
            # Simple alpha compositing: trail += prev (clamped)
            trail_rgba = np.clip(trail_rgba + prev * trail_alpha_scale, 0, 1)
        trail_im.set_data(trail_rgba)

        # Update beam label
        beam_lbl.set_text(f"beam {bid}")

        # Highlight current beam dot in blue, others grey
        for b, dot in dot_artists.items():
            if b == bid:
                dot.set_color("#1a4e8a")
                dot.set_alpha(1.0)
                dot.set_markersize(3.5)
            elif b in [beam_ids[j] for j in range(frame_idx)]:
                dot.set_color("steelblue")
                dot.set_alpha(0.5)
                dot.set_markersize(2.0)
            else:
                dot.set_color("0.6")
                dot.set_alpha(0.3)
                dot.set_markersize(2.0)

        return [trail_im, current_im, beam_lbl] + list(dot_artists.values())

    ani = animation.FuncAnimation(
        fig, update, frames=total_frames,
        interval=1000 // fps, blit=True,
    )

    # ── Write MP4 ────────────────────────────────────────────────────────────
    output_path = str(output_path)
    import shutil
    if shutil.which("ffmpeg") is None:
        print("WARNING: ffmpeg not found on PATH — saving as GIF instead.")
        gif_path = output_path.replace(".mp4", ".gif")
        ani.save(gif_path, writer="pillow", fps=fps, dpi=dpi)
        print(f"Saved → {gif_path}")
    else:
        writer = animation.FFMpegWriter(
            fps=fps, codec="h264",
            extra_args=["-pix_fmt", "yuv420p", "-crf", "18"],
        )
        ani.save(output_path, writer=writer, dpi=dpi)
        size_kb = Path(output_path).stat().st_size // 1024
        print(f"Saved → {output_path}  ({size_kb} KB)")

    plt.close(fig)


# ── CLI ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Animate closepack-36 beams on PAF layout (Airy pattern, MP4)"
    )
    parser.add_argument("--footprint",  required=True,
                        help="footprintOutput-sb<N>-<FIELD>.txt")
    parser.add_argument("--schedblock", required=True,
                        help="schedblock-info-<N>.txt")
    parser.add_argument("--output",     default="paf_beam_movie.mp4",
                        help="Output MP4 path (default: paf_beam_movie.mp4)")
    parser.add_argument("--fps",        type=int, default=2,
                        help="Frames per second (default: 2)")
    parser.add_argument("--n-nulls",    type=int, default=3, choices=[1, 2, 3],
                        help="Airy null radius to display (default: 3)")
    parser.add_argument("--trail",      type=float, default=0.22,
                        help="Trail alpha scale factor 0–1 (default: 0.22)")
    parser.add_argument("--gamma",      type=float, default=0.45,
                        help="Display gamma for Airy rings (default: 0.45)")
    parser.add_argument("--cmap",       default="gray",
                        help="Matplotlib colourmap for Airy pattern (default: gray)")
    parser.add_argument("--dpi",        type=int, default=150,
                        help="Output resolution DPI (default: 150)")
    parser.add_argument("--grid-res",   type=int, default=500,
                        help="Airy grid resolution in pixels (default: 500)")
    parser.add_argument("--hold",       type=int, default=2,
                        help="Extra hold frames at end (default: 2)")
    parser.add_argument("--freq-mhz",   type=float, default=None,
                        help="Override centre frequency (MHz)")
    parser.add_argument("--elem-pitch", type=float, default=None,
                        help="Override element pitch (deg)")
    parser.add_argument("--dish-diam",  type=float, default=None,
                        help="Override dish diameter (m)")
    args = parser.parse_args()

    build_movie(
        footprint_path      = args.footprint,
        schedblock_path     = args.schedblock,
        output_path         = args.output,
        fps                 = args.fps,
        n_nulls             = args.n_nulls,
        trail_alpha_scale   = args.trail,
        gamma               = args.gamma,
        cmap_name           = args.cmap,
        dpi                 = args.dpi,
        grid_res            = args.grid_res,
        hold_frames         = args.hold,
        freq_mhz_override   = args.freq_mhz,
        elem_pitch_override = args.elem_pitch,
        dish_diam_override  = args.dish_diam,
    )


if __name__ == "__main__":
    main()
