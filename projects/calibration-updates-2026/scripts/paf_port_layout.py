"""
paf_port_layout.py

Generates the exact MkII PAF port layout on a 12×11 rectilinear grid
(12 columns, 11 rows) based on the Reynolds coordinate system and
the port numbering scheme, then renders it as a static PNG and as
a 4-panel beam overlay (all flip combinations).

Grid conventions (rear view: Leg2 top-left, Leg1 top-right):
  - Columns  1–12  left → right  (col 12 = Leg1 side)
  - Rows     1–11  top  → bottom (row 1  = Leg2/Leg1 side; row 11 = Leg3/Leg4 side)
  - X-pol port numbers increase RIGHT → LEFT (port 1 rightmost in row 1)
  - Y-pol ports are the orthogonal counterpart: same grid positions,
    numbered 95–188 in the same spatial sequence.

Row layout (active columns for x-pol, 0-indexed col = 1..12):
  Row  1: cols 5–8   (4 ports  → 1–4)
  Row  2: cols 3–10  (8 ports  → 5–12)
  Row  3: cols 2–11  (10 ports → 13–22)
  Row  4: cols 2–11  (10 ports → 23–32)
  Row  5: cols 2–11  (10 ports → 33–42)  [cols 1,12 = unused physical sockets]
  Row  6: cols 2–11  (10 ports → 43–52)  [cols 1,12 = unused physical sockets]
  Row  7: cols 2–11  (10 ports → 53–62)  [cols 1,12 = unused physical sockets]
  Row  8: cols 2–11  (10 ports → 63–72)
  Row  9: cols 2–11  (10 ports → 73–82)
  Row 10: cols 3–10  (8 ports  → 83–90)
  Row 11: cols 5–8   (4 ports  → 91–94)

Unused sockets (rows 5–7, cols 1 and 12) are shown as empty outlines.
"""

import numpy as np
import re
import matplotlib as mpl
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.patheffects as mpe
from typing import Optional

# ─── Grid definition ──────────────────────────────────────────────────────────

# Row spec: (row_number, first_active_col, last_active_col)
# 12×12 symmetric grid — 112 elements total:
#   col 1,12 : rows 5–8   →  4 elements each
#   col 2,11 : rows 3–10  →  8 elements each
#   col 3,4,9,10: rows 2–11 → 10 elements each
#   col 5–8  : rows 1–12  → 12 elements each
# Equivalently by row:
#   row 1,12 : cols 5–8   →  4 elements
#   row 2,11 : cols 3–10  →  8 elements
#   row 3,4,9,10: cols 2–11 → 10 elements
#   row 5–8  : cols 1–12  → 12 elements
ROW_SPEC = [
    ( 1,  5,  8),
    ( 2,  3, 10),
    ( 3,  2, 11),
    ( 4,  2, 11),
    ( 5,  1, 12),
    ( 6,  1, 12),
    ( 7,  1, 12),
    ( 8,  1, 12),
    ( 9,  2, 11),
    (10,  2, 11),
    (11,  3, 10),
    (12,  5,  8),
]

# Leg colour by quadrant (rear view: Leg2=upper-left, Leg1=upper-right,
#                                    Leg3=lower-left, Leg4=lower-right/red)
# Quadrant boundary: col<=6 vs col>=7  and  row<=5 vs row>=6 (rough centre)
LEG_COLOUR = {
    "R": "#dd4444",   # top wedge    (between Leg1 and Leg2)
    "G": "#44aa44",   # left wedge   (between Leg2 and Leg3)
    "B": "#4466cc",   # bottom wedge (between Leg3 and Leg4)
    "Y": "#ccaa00",   # right wedge  (between Leg4 and Leg1)
}

def _leg_colour(row: int, col: int) -> str:
    """
    Assign leg colour by diagonal quadrant using physical (device) coordinates.
    Always uses rear-view formula so leg colours are independent of the
    display convention chosen in grid_to_xy.

    Device-frame diagonal boundaries (rear-view, x=col-6.5, y=6.5-row):
      x+y > 0  AND  y-x > 0  →  top    wedge → "R" (between Leg1 & Leg2)
      x+y < 0  AND  y-x > 0  →  left   wedge → "G" (between Leg2 & Leg3)
      x+y < 0  AND  y-x < 0  →  bottom wedge → "B" (between Leg3 & Leg4)
      x+y > 0  AND  y-x < 0  →  right  wedge → "Y" (between Leg4 & Leg1)
    """
    # Physical rear-view coordinates (decoupled from display grid_to_xy)
    x = col - 6.5
    y = 6.5 - row
    sp = x + y
    sm = y - x
    if sp >= 0 and sm >= 0: return "R"   # top    wedge (between Leg1 & Leg2)
    if sp <  0 and sm >= 0: return "G"   # left   wedge (between Leg2 & Leg3)
    if sp <  0 and sm <  0: return "B"   # bottom wedge (between Leg3 & Leg4)
    return "Y"                            # right  wedge (between Leg4 & Leg1)


def build_port_table() -> dict:
    """
    Build a placeholder port table (row, col, pol) for all 112 elements.
    Port numbering will be assigned in a later step.
    Returns port_table dict and an empty unused_sockets set.
    """
    port_to_grid = {}
    idx = 1
    for (row, c_start, c_end) in ROW_SPEC:
        for col in range(c_end, c_start - 1, -1):   # right → left
            port_to_grid[idx]      = (row, col, 'X')
            port_to_grid[idx + 112] = (row, col, 'Y')
            idx += 1
    return port_to_grid, set()   # no unused sockets in this layout


def grid_to_xy(row: int, col: int):
    """
    Convert (row, col) in 1-based 12×12 grid to sky-view plot (x,y).
    Sky-view convention: sky-North = up, sky-East = right.
    x increases rightward (col decreases: col 1 → right, col 12 → left).
    y increases upward   (row increases: row 12 → top,  row 1  → bottom).
    Returns centred coordinates so (0,0) = centre of 12×12 grid.
    """
    x = 6.5 - col    # cols 1–12; col 1 at right (+5.5), col 12 at left (−5.5)
    y = row - 6.5    # rows 1–12; row 12 at top (+5.5), row 1 at bottom (−5.5)
    return x, y


# ─── Plot helpers ─────────────────────────────────────────────────────────────

ELEM_SIZE    = 0.42   # half-size of each diamond marker (grid units)
ARM_LEN      = 0.28   # arm extension beyond diamond corner to port-dot
DOT_SIZE     = 4.0    # port-dot marker size (pt)
PORT_FONTSIZE = 3.8


def _active_cols(row: int) -> set:
    """Return the set of active columns for *row* (1-based)."""
    for (r, c_start, c_end) in ROW_SPEC:
        if r == row:
            return set(range(c_start, c_end + 1))
    return set()


def _active_rows(col: int) -> set:
    """Return the set of active rows for *col* (1-based), derived from ROW_SPEC."""
    rows = set()
    for (r, c_start, c_end) in ROW_SPEC:
        if c_start <= col <= c_end:
            rows.add(r)
    return rows


def build_xport_map() -> dict:
    """
    Build the x-port numbering: {(upper_row, col): port_number 1..94}.

    Numbering rule (agreed with user):
      Iterate row-pairs top→bottom (rows 1-2, 2-3, ..., 11-12).
      Within each pair take the shared cols, exclude col 1 and col 12,
      sort RIGHT→LEFT (descending col), and assign sequential port numbers.
    """
    xport_map = {}
    port_num = 1
    for upper_row in range(1, 12):
        lower_row = upper_row + 1
        shared = _active_cols(upper_row) & _active_cols(lower_row)
        usable = sorted(shared - {1, 12}, reverse=True)   # right → left, skip 1&12
        for col in usable:
            xport_map[(upper_row, col)] = port_num
            port_num += 1
    assert port_num - 1 == 94, f"Expected 94 x-ports, got {port_num - 1}"
    return xport_map


def build_yport_map() -> dict:
    """
    Build the y-port numbering: {(row, left_col): port_number 95..188}.

    Numbering rule (symmetric with x-ports):
      Iterate col-pairs left→right (cols 1-2, 2-3, ..., 11-12).
      Within each pair take the shared rows, exclude row 1 and row 12,
      sort TOP→BOTTOM (ascending row), and assign sequential port numbers
      starting at 95.
    """
    yport_map = {}
    port_num = 95
    for left_col in range(1, 12):
        right_col = left_col + 1
        shared = _active_rows(left_col) & _active_rows(right_col)
        usable = sorted(shared - {1, 12})   # top → bottom, skip rows 1 & 12
        for row in usable:
            yport_map[(row, left_col)] = port_num
            port_num += 1
    assert port_num - 1 == 188, f"Expected 188 as last y-port, got {port_num - 1}"
    return yport_map


# ─── Beam footprint overlay ───────────────────────────────────────────────────

DEFAULT_FOOTPRINT = (
    "/Users/raj030/DATA/reffield-average/"
    "SB_REF-81084_SB_1934-77045_SB_HOLO-76554_AMP_STRATEGY-multiply-insituPreflags/"
    "metadata/footprintOutput-sb81084-REF_0324-28.txt"
)
DEFAULT_PITCH_DEG      = 0.9
DEFAULT_ELEM_PITCH_DEG = DEFAULT_PITCH_DEG / 1.329   # ≈ 0.677°
# footprint.rotation in the schedblock is 45°, which with rotation_sign=-1
# gives an effective PAF-frame rotation of -45° — confirmed to place beam 0
# in the Leg4/yellow (lower-right) quadrant of the rear-view PAF.
# No additional Leg4 offset is needed; 45° is the correct raw input.


def parse_footprint_output(filepath: str) -> dict:
    """
    Parse a footprintOutput file.
    Returns {beam_id (int): (x_sky_deg, y_sky_deg)}.
    Format: `<id>  (<x> <y>)  RA,Dec`
    """
    beams = {}
    pattern = re.compile(r'^\s*(\d+)\s+\(\s*(-?[\d.]+)\s+(-?[\d.]+)\s*\)')
    with open(filepath) as fh:
        for line in fh:
            m = pattern.match(line)
            if m:
                bid = int(m.group(1))
                x   = float(m.group(2))
                y   = float(m.group(3))
                beams[bid] = (x, y)
    if not beams:
        raise ValueError(f"No beams parsed from {filepath}")
    return beams


def sky_to_paf_grid(beams: dict,
                    pitch_deg:     float = DEFAULT_PITCH_DEG,
                    elem_pitch_deg: float = DEFAULT_ELEM_PITCH_DEG,
                    pol_axis_deg:  float = 0.0) -> dict:
    """
    Project sky-frame beam offsets (x_sky=East, y_sky=North, degrees) onto
    the PAF rear-view grid using the physically-motivated compass transform.

    Physics:
      - pol_axis_deg is a sky position angle (North-through-East), maintained
        fixed on the sky by ASKAP's third (roll) axis in pa_fixed mode.
      - Telescope prime focus inverts the sky image: (x_sky, y_sky) →
        (-x_sky, -y_sky) on the focal plane.
      - Rear-view orientation adds a left-right mirror: East on sky appears
        to the LEFT in the rear-view diagram (toward Leg 3).
      - Combined effect: angle of North in rear-view = +45° - pol_axis_deg
        from the +u axis (Leg 4 at lower-right = +45° from horizontal at
        pol_axis=0 in rear view after applying both inversions).
      - East on PAF rear-view: 90° clockwise from North.
    """
    scale = pitch_deg / elem_pitch_deg
    na    = np.radians(+45.0 - pol_axis_deg)
    nd    = np.array([np.cos(na),  np.sin(na)])   # North unit vector
    ed    = np.array([nd[1],      -nd[0]])          # East  unit vector (90° CW in rear view)
    result = {}
    for bid, (x_sky, y_sky) in beams.items():
        u = scale / pitch_deg * (-y_sky * nd[0] - x_sky * ed[0])
        v = scale / pitch_deg * (-y_sky * nd[1] - x_sky * ed[1])
        # Negate both to convert rear-view focal-plane to sky-view (N up, E right)
        result[bid] = (float(-u), float(-v))
    return result


def overlay_beam_footprint(ax: plt.Axes,
                           footprint_file: str  = DEFAULT_FOOTPRINT,
                           pitch_deg: float     = DEFAULT_PITCH_DEG,
                           elem_pitch_deg: float = DEFAULT_ELEM_PITCH_DEG,
                           beam_fwhm_deg: float = 1.0,
                           pol_axis_deg: float  = 0.0) -> dict:
    """
    Overlay closepack36 beam circles on the PAF rear-view diagram.

    Uses the compass-based sky→PAF transform (same physics as the South-star
    marker): telescope inversion + PAF orientation set by pol_axis_deg.
    Returns {beam_id: (u_grid, v_grid)}.
    """
    beams_sky = parse_footprint_output(footprint_file)
    beams_paf = sky_to_paf_grid(beams_sky,
                                 pitch_deg      = pitch_deg,
                                 elem_pitch_deg = elem_pitch_deg,
                                 pol_axis_deg   = pol_axis_deg)

    radius_grid = (beam_fwhm_deg / 2.0) / elem_pitch_deg

    n = len(beams_paf)
    beam_colour = '#888888'
    for bid in sorted(beams_paf):
        u, v = beams_paf[bid]
        circ = plt.Circle((u, v), radius_grid,
                           color=beam_colour, fill=True,
                           alpha=0.45, linewidth=1.2, zorder=8)
        ax.add_patch(circ)
        circ_edge = plt.Circle((u, v), radius_grid,
                                color=beam_colour, fill=False,
                                alpha=0.95, linewidth=1.2, zorder=9)
        ax.add_patch(circ_edge)
        ax.text(u, v, str(bid), ha='center', va='center',
                fontsize=6.5, fontweight='bold', color='black', zorder=10,
                path_effects=[mpe.withStroke(linewidth=2.0, foreground='white')])

    print(f"Overlaid {n} beams  (pol_axis={pol_axis_deg:+.1f}°, sky-view: N up, E right)")
    return beams_paf


def draw_paf_elements(ax: plt.Axes,
                      port_table: dict,
                      unused_sockets: set,
                      show_port_numbers: bool = True,
                      alpha_elem: float = 0.08,
                      alpha_unused: float = 0.03) -> None:
    """
    Draw all 112 PAF elements on *ax* in rear-view frame.

    Each element (diamond) has FOUR arms:
      • Top/bottom arms  → x-pol connections (vertical, between rows)
      • Left/right arms  → y-pol connections (horizontal, between cols)

    Port dots:
      • X-pol connection dots: COLOURED only for cols 2–11 (94 physical ports)
        Col 1 and col 12 vertical connections are GREY (not physically used)
      • Y-pol connection dots: COLOURED only for rows 2–11 (94 physical ports)
        Row 1 and row 12 horizontal connections are GREY (not physically used)
      • Unpaired edge arm-tips: GREY with no label
    """
    # Build correct x-port numbering map: (upper_row, col) → port 1..94
    xport_map = build_xport_map()
    # Build correct y-port numbering map: (row, left_col) → port 95..188
    yport_map = build_yport_map()

    # {(row,col)} set of active element positions
    elem_pos: set = set()
    for port, (row, col, pol) in port_table.items():
        if pol == 'X':
            elem_pos.add((row, col))

    # ── Step 1: diamonds + all four arms ─────────────────────────────────────
    for (row, col) in sorted(elem_pos):
        x, y = grid_to_xy(row, col)
        ckey = _leg_colour(row, col)
        fc = (*mpl.colors.to_rgb(LEG_COLOUR[ckey]), alpha_elem)
        ec = LEG_COLOUR[ckey]

        verts = [(x + ELEM_SIZE, y),
                 (x,             y + ELEM_SIZE),
                 (x - ELEM_SIZE, y),
                 (x,             y - ELEM_SIZE)]
        ax.add_patch(mpatches.Polygon(
            verts, closed=True, lw=0.7,
            edgecolor=ec, facecolor=fc, zorder=2))

        # top arm (x-pol)
        ax.plot([x, x], [y + ELEM_SIZE, y + ELEM_SIZE + ARM_LEN],
                color=ec, lw=0.75, zorder=3)
        # bottom arm (x-pol)
        ax.plot([x, x], [y - ELEM_SIZE, y - ELEM_SIZE - ARM_LEN],
                color=ec, lw=0.75, zorder=3)
        # right arm (y-pol)
        ax.plot([x + ELEM_SIZE, x + ELEM_SIZE + ARM_LEN], [y, y],
                color=ec, lw=0.75, zorder=3)
        # left arm (y-pol)
        ax.plot([x - ELEM_SIZE, x - ELEM_SIZE - ARM_LEN], [y, y],
                color=ec, lw=0.75, zorder=3)

    drawn: set = set()

    # ── Step 2: X-pol dots (vertical connections, between rows) ──────────────
    for row in range(1, 13):
        cols_this = _active_cols(row)
        cols_prev = _active_cols(row - 1) if row > 1  else set()
        cols_next = _active_cols(row + 1) if row < 12 else set()

        # Shared dot: bottom-arm of (row-1) meets top-arm of (row)
        for col in sorted(cols_this & cols_prev, reverse=True):
            key = (row - 1, col, 'xbot')
            if key in drawn:
                continue
            drawn.add(key)
            x, y_this = grid_to_xy(row,     col)
            _, y_prev  = grid_to_xy(row - 1, col)
            y_dot = 0.5 * ((y_prev - ELEM_SIZE - ARM_LEN) +
                            (y_this + ELEM_SIZE + ARM_LEN))
            # Physical x-port only for cols 2–11
            is_physical = (2 <= col <= 11)
            ckey = _leg_colour(row - 1, col)
            dot_color = LEG_COLOUR[ckey] if is_physical else '0.70'
            dot_ec    = '0.20'           if is_physical else '0.50'
            ax.plot(x, y_dot, 'o',
                    ms=DOT_SIZE, color=dot_color,
                    markeredgewidth=0.4, markeredgecolor=dot_ec,
                    zorder=5)
            if show_port_numbers and is_physical:
                xport = xport_map.get((row - 1, col))
                if xport is not None:
                    ax.text(x + 0.26, y_dot, str(xport),
                            ha='left', va='center',
                            fontsize=PORT_FONTSIZE, color='0.15',
                            fontweight='bold', zorder=6)

        # Unpaired top-arm dots
        for col in sorted(cols_this - cols_prev, reverse=True):
            key = (row, col, 'xtop')
            if key in drawn:
                continue
            drawn.add(key)
            x, y_this = grid_to_xy(row, col)
            ax.plot(x, y_this + ELEM_SIZE + ARM_LEN, 'o',
                    ms=DOT_SIZE * 0.75, color='0.72',
                    markeredgewidth=0.3, markeredgecolor='0.50', zorder=4)

        # Unpaired bottom-arm dots
        for col in sorted(cols_this - cols_next, reverse=True):
            key = (row, col, 'xbot')
            if key in drawn:
                continue
            drawn.add(key)
            x, y_this = grid_to_xy(row, col)
            ax.plot(x, y_this - ELEM_SIZE - ARM_LEN, 'o',
                    ms=DOT_SIZE * 0.75, color='0.72',
                    markeredgewidth=0.3, markeredgecolor='0.50', zorder=4)

    # ── Step 3: Y-pol dots (horizontal connections, between cols) ─────────────
    for col in range(1, 13):
        rows_this = _active_rows(col)
        rows_prev = _active_rows(col - 1) if col > 1  else set()
        rows_next = _active_rows(col + 1) if col < 12 else set()

        # Shared dot: right-arm of (col-1) meets left-arm of (col)
        for row in sorted(rows_this & rows_prev):
            key = (row, col - 1, 'yright')
            if key in drawn:
                continue
            drawn.add(key)
            x_this, y = grid_to_xy(row, col)
            x_prev, _  = grid_to_xy(row, col - 1)
            x_dot = 0.5 * ((x_prev + ELEM_SIZE + ARM_LEN) +
                            (x_this - ELEM_SIZE - ARM_LEN))
            # Physical y-port only for rows 2–11
            is_physical = (2 <= row <= 11)
            ckey = _leg_colour(row, col - 1)
            dot_color = LEG_COLOUR[ckey] if is_physical else '0.70'
            dot_ec    = '0.20'           if is_physical else '0.50'
            ax.plot(x_dot, y, 's',          # square marker distinguishes y-pol
                    ms=DOT_SIZE * 0.90, color=dot_color,
                    markeredgewidth=0.4, markeredgecolor=dot_ec,
                    zorder=5)
            if show_port_numbers and is_physical:
                yport = yport_map.get((row, col - 1))
                if yport is not None:
                    ax.text(x_dot, y + 0.26, str(yport),
                            ha='center', va='bottom',
                            fontsize=PORT_FONTSIZE, color='#885500',
                            fontweight='bold', zorder=6)

        # Unpaired right-arm dots
        for row in sorted(rows_this - rows_prev):
            key = (row, col, 'yleft')
            if key in drawn:
                continue
            drawn.add(key)
            x_this, y = grid_to_xy(row, col)
            ax.plot(x_this - ELEM_SIZE - ARM_LEN, y, 's',
                    ms=DOT_SIZE * 0.65, color='0.72',
                    markeredgewidth=0.3, markeredgecolor='0.50', zorder=4)

        # Unpaired left-arm dots
        for row in sorted(rows_this - rows_next):
            key = (row, col, 'yright')
            if key in drawn:
                continue
            drawn.add(key)
            x_this, y = grid_to_xy(row, col)
            ax.plot(x_this + ELEM_SIZE + ARM_LEN, y, 's',
                    ms=DOT_SIZE * 0.65, color='0.72',
                    markeredgewidth=0.3, markeredgecolor='0.50', zorder=4)

    # ── Step 4: faint grid reference lines ────────────────────────────────────
    for col in range(1, 13):
        xg, _ = grid_to_xy(1, col)
        ax.axvline(xg, lw=0.12, color='0.88', zorder=0)
    for row in range(1, 13):
        _, yg = grid_to_xy(row, 1)
        ax.axhline(yg, lw=0.12, color='0.88', zorder=0)

    # ── Step 5: leg arrows and wedge labels ───────────────────────────────────
    wedge_labels = {
        'R': ( 0.0, -5.5, 'center', 'top'),      # Leg1/Leg2 side: bottom in sky-view
        'G': ( 5.5,  0.0, 'left',   'center'),   # Leg2/Leg3 side: right  in sky-view
        'B': ( 0.0,  5.5, 'center', 'bottom'),   # Leg3/Leg4 side: top    in sky-view
        'Y': (-5.5,  0.0, 'right',  'center'),   # Leg4/Leg1 side: left   in sky-view
    }
    leg_positions = {
        'Leg 1\n(+90°)':  (-6.2, -5.8, 'right', 'top',    '0.35', '0.30'),
        'Leg 2\n(180°)':  ( 6.2, -5.8, 'left',  'top',    '0.35', '0.30'),
        'Leg 3\n(−90°)':  ( 6.2,  5.8, 'left',  'bottom', '0.35', '0.30'),
        'Leg 4\n(0°)':    (-6.2,  5.8, 'right', 'bottom', 'red',  'red'),
    }
    for lbl, (tx, ty, ha, va) in wedge_labels.items():
        ax.text(tx, ty, lbl, ha=ha, va=va, fontsize=13,
                color=LEG_COLOUR[lbl], alpha=0.22, fontweight='bold', zorder=0)
    for lbl, (tx, ty, ha, va, arrow_c, text_c) in leg_positions.items():
        ax.annotate('', xy=(tx * 0.72, ty * 0.72), xytext=(tx * 0.95, ty * 0.95),
                    arrowprops=dict(arrowstyle='->', color=arrow_c, lw=1.0),
                    annotation_clip=False, zorder=6)
        ax.text(tx, ty, lbl, ha=ha, va=va,
                fontsize=7, color=text_c, fontweight='bold')


def frame_axis(ax: plt.Axes, title: str = "") -> None:
    ax.set_xlim(-8.0, 8.0)
    ax.set_ylim(-8.0, 8.0)   # extra room for beam circles at array edge
    ax.set_aspect('equal')
    ax.plot(0, 0, 'k+', ms=8, mew=1.5, zorder=7)
    ax.set_title(title, fontsize=9, pad=3)
    ax.tick_params(labelsize=6)
    ax.set_xlabel("← Leg1/Leg2      col      Leg3/Leg4 side →  [sky-East right]", fontsize=7)
    ax.set_ylabel("← Leg1/Leg2      row      Leg3/Leg4 side ↑  [sky-North up]",   fontsize=7)
    ax.text(0.01, 0.01, "Sky view (N up, E right)\nLeg4=upper-left  Leg3=upper-right",
            transform=ax.transAxes, fontsize=5.5, color='0.45', va='bottom')


# ─── Main: generate layout plot ───────────────────────────────────────────────

def _draw_sky_overlay(ax: plt.Axes, pol_axis_deg: float,
                      star_dist_pitches: float = 3.0,
                      compass_origin: tuple = (-6.5, 6.0),
                      arrow_len: float = 1.2) -> None:
    """Draw pointing star, south-sky star and N/E compass for a given pol_axis."""
    # North direction on PAF rear-view:
    #   Combined prime-focus inversion + rear-view mirror: angle = +45° - pol_axis_deg
    #   (canonical formula — matches sky_to_paf_grid() in this file)
    north_angle_rad = np.radians(+45.0 - pol_axis_deg)
    nd = np.array([np.cos(north_angle_rad), np.sin(north_angle_rad)])
    ed = np.array([nd[1], -nd[0]])   # East = 90° CW from North in rear-view

    _scale = DEFAULT_PITCH_DEG / DEFAULT_ELEM_PITCH_DEG
    _dist  = star_dist_pitches * _scale

    # Red star: pointing direction (always at centre)
    ax.plot(0, 0, marker='*', markersize=18, color='red',
            markeredgecolor='darkred', markeredgewidth=0.8, zorder=20)
    ax.text(0.22, 0.15, 'pointing', fontsize=5.5, color='darkred',
            fontweight='bold', ha='left', va='bottom', zorder=21)

    # Gold star: sky-North source → appears in North (up) direction in sky-view
    u_s, v_s = _dist * nd
    ax.plot(u_s, v_s, marker='*', markersize=18, color='gold',
            markeredgecolor='darkorange', markeredgewidth=1.0, zorder=20)
    ax.text(u_s + 0.22, v_s, 'N sky\nsource', fontsize=5.5,
            color='darkorange', fontweight='bold', ha='left', va='center', zorder=21)

    # Cyan star: sky-East source → appears in East (right) direction in sky-view
    u_w, v_w = _dist * ed
    ax.plot(u_w, v_w, marker='*', markersize=18, color='cyan',
            markeredgecolor='teal', markeredgewidth=1.0, zorder=20)
    ax.text(u_w + 0.22, v_w, 'E sky\nsource', fontsize=5.5,
            color='teal', fontweight='bold', ha='left', va='center', zorder=21)

    # Compass rose
    org = np.array(compass_origin)
    for vec, label in [(nd, 'N'), (ed, 'E')]:
        ax.annotate("", xy=org + arrow_len * vec, xytext=org,
                    arrowprops=dict(arrowstyle='->', color='navy', lw=1.8), zorder=25)
        ax.text(*(org + (arrow_len + 0.3) * vec), label, color='navy',
                fontsize=8, fontweight='bold', ha='center', va='center', zorder=25)
    ax.text(org[0], org[1] - 1.7, f'pol_axis={pol_axis_deg:+.0f}°',
            color='navy', fontsize=6, ha='center', va='top', style='italic', zorder=25)


def plot_paf_layout(output: str         = "/tmp/paf_layout_overlay.png",
                    footprint_file: str = DEFAULT_FOOTPRINT,
                    pol_axis_deg: float = 0.0) -> None:
    port_table, unused_sockets = build_port_table()
    n_active = len([p for p in port_table if port_table[p][2] == 'X'])
    print(f"Active elements (x-pol): {n_active}")
    print(f"Total entries (x+y):     {len(port_table)}")

    fig, ax = plt.subplots(figsize=(12, 10), facecolor='white')
    draw_paf_elements(ax, port_table, unused_sockets, show_port_numbers=True)
    if footprint_file:
        overlay_beam_footprint(ax, footprint_file=footprint_file, pol_axis_deg=pol_axis_deg)
    _draw_sky_overlay(ax, pol_axis_deg)
    frame_axis(ax, "MkII PAF 112-element / 188-port layout on 12×12 grid (rear view)\n"
                   "● x-ports 1–94 (vertical, cols 2–11)   "
                   "■ y-ports 95–188 (horizontal, rows 2–11)   "
                   "grey = unconnected arm   circles = closepack36 beams")
    fig.tight_layout()
    fig.savefig(output, dpi=180, bbox_inches='tight')
    plt.close(fig)
    print(f"Saved → {output}")
    return port_table, unused_sockets


def plot_paf_polaxis_panels(output:         str   = "/tmp/paf_polaxis_panels.png",
                            pol_axis_list:  list  = (0, 45, 60, -45),
                            footprint_file: str   = None) -> None:
    """2×2 panel plot showing how the sky orientation and south-star move with pol_axis."""
    port_table, unused_sockets = build_port_table()

    fig, axes = plt.subplots(2, 2, figsize=(18, 16), facecolor='white')
    fig.suptitle("MkII PAF — sky orientation for different pol_axis values (rear view)\n"
                 "Red ★ = pointing direction   Gold ★ = source 3 beam-pitches South of pointing",
                 fontsize=11, y=1.01)

    for ax, pa in zip(axes.flat, pol_axis_list):
        draw_paf_elements(ax, port_table, unused_sockets, show_port_numbers=False)
        if footprint_file:
            overlay_beam_footprint(ax, footprint_file=footprint_file)
        _draw_sky_overlay(ax, pa, compass_origin=(-6.2, 5.8), arrow_len=1.1)
        frame_axis(ax, f"pol_axis = {pa:+.0f}°")

    fig.tight_layout()
    fig.savefig(output, dpi=150, bbox_inches='tight')
    plt.close(fig)
    print(f"Saved → {output}")


def plot_paf_polaxis_footprint_panels(output:        str  = "/tmp/paf_polaxis_footprint_panels.png",
                                      pol_axis_list: list = (0, 45, 60, -45),
                                      footprint_file: str = DEFAULT_FOOTPRINT) -> None:
    """2x2 panel: beam footprint + sky markers for 4 pol_axis values."""
    port_table, unused_sockets = build_port_table()
    fig, axes = plt.subplots(2, 2, figsize=(18, 16), facecolor='white')
    fig.suptitle(
        "MkII PAF — closepack36 beam footprint for different pol_axis values (rear view)\n"
        "Red ★ = pointing direction   Gold ★ = source 3 pitches South of pointing",
        fontsize=11, y=1.01)
    for ax, pa in zip(axes.flat, pol_axis_list):
        draw_paf_elements(ax, port_table, unused_sockets, show_port_numbers=False)
        overlay_beam_footprint(ax, footprint_file=footprint_file, pol_axis_deg=pa)
        _draw_sky_overlay(ax, pa, compass_origin=(-6.2, 5.8), arrow_len=1.1)
        frame_axis(ax, f"pol_axis = {pa:+.0f}°")
    fig.tight_layout()
    fig.savefig(output, dpi=150, bbox_inches='tight')
    plt.close(fig)
    print(f"Saved → {output}")


if __name__ == "__main__":
    plot_paf_polaxis_footprint_panels()
