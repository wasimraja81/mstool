#!/usr/bin/env python3
"""
Visualise the 3-D leakage cube as faceted footprint plots.

Each panel shows one (ODC, variant) combination.  Beams are drawn as
circles at their physical footprint positions (relative offsets in
degrees from the footprint metadata).  Circle colour encodes dL (%).

Usage
-----
    python plot_leakage_footprint.py [--data-root ~/DATA/reffield-average]
                                     [--field REF_0324-28]

Produces one PNG per reference field under <data-root>/phase3/plots/.
If --field is omitted, all fields are plotted.
"""

import argparse
import re
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import xarray as xr
from matplotlib.collections import PatchCollection
from matplotlib.patches import Circle, Wedge


# ── Parse beam offsets from a footprintOutput file ──────────────────────
def parse_footprint(fp_path: Path):
    """Return dict  beam_index -> (x_deg, y_deg)  from a footprintOutput file."""
    offsets = {}
    pattern = re.compile(
        r"^\s*(\d+)\s+\(\s*([-\d.]+)\s+([-\d.]+)\s*\)"
    )
    for line in fp_path.read_text().splitlines():
        m = pattern.match(line)
        if m:
            beam = int(m.group(1))
            x = float(m.group(2))
            y = float(m.group(3))
            offsets[beam] = (x, y)
    return offsets


def load_and_validate_footprint(data_root: Path, atol=1e-6):
    """
    Load ALL footprintOutput-*.txt files, validate that beam offsets are
    identical across every SB_REF, and return the consensus offsets.

    Raises RuntimeError if any footprint disagrees.
    Returns dict  beam_index -> (x_deg, y_deg).
    """
    fp_files = sorted(
        fp for fp in data_root.glob("SB_REF-*/metadata/footprintOutput-*.txt")
        if "src1" not in fp.name
    )
    if not fp_files:
        raise FileNotFoundError("No footprintOutput-*.txt found under data root")

    reference = None      # dict beam -> (x, y)
    reference_file = None  # path of the first file used as reference

    for fp in fp_files:
        offsets = parse_footprint(fp)
        if not offsets:
            print(f"  WARNING: empty footprint in {fp} — skipping")
            continue

        if reference is None:
            reference = offsets
            reference_file = fp
            continue

        # Validate: every beam present in this file must match the reference
        for beam, (x, y) in offsets.items():
            if beam not in reference:
                raise RuntimeError(
                    f"Footprint inconsistency: beam {beam} present in\n"
                    f"  {fp}\n"
                    f"but absent from reference\n"
                    f"  {reference_file}"
                )
            rx, ry = reference[beam]
            if abs(x - rx) > atol or abs(y - ry) > atol:
                raise RuntimeError(
                    f"Footprint MISMATCH for beam {beam}:\n"
                    f"  {reference_file}: ({rx}, {ry})\n"
                    f"  {fp}: ({x}, {y})\n"
                    f"Beam offsets differ by ({x - rx:.6f}, {y - ry:.6f}) deg.\n"
                    f"Cannot proceed — footprints are not consistent across SB_REFs."
                )

        # Also check if reference has beams not in this file (just warn)
        for beam in reference:
            if beam not in offsets:
                print(
                    f"  NOTE: beam {beam} in reference {reference_file.name} "
                    f"but absent from {fp.name} (OK if subset)"
                )

    print(f"Validated {len(fp_files)} footprint files — all consistent.")
    print(f"  Reference: {reference_file.name}  ({len(reference)} beams)")
    return reference


def plot_single_panel(ds, offsets, field_name, odc_val, var_name, var_label,
                      output_dir, vmin=0, vmax=1.5):
    """
    Plot a single footprint panel for one (field, ODC, variant) combination.
    Returns the output Path (or None if no data).
    """
    if var_name not in ds:
        return None

    sl = ds[var_name].sel(field=field_name, odc=odc_val)
    vals = sl.values
    if np.all(np.isnan(vals)):
        return None

    beams = ds.beam.values
    xs = np.array([offsets.get(int(b), (np.nan, np.nan))[0] for b in beams])
    ys = np.array([offsets.get(int(b), (np.nan, np.nan))[1] for b in beams])

    dists = []
    for i in range(len(xs)):
        for j in range(i + 1, len(xs)):
            d = np.hypot(xs[i] - xs[j], ys[i] - ys[j])
            if d > 0:
                dists.append(d)
    radius = min(dists) / 2.0 if dists else 0.4

    cmap = plt.cm.RdYlGn_r

    fig, ax = plt.subplots(figsize=(5.5, 5.5))

    patches = []
    colors = []
    for k, b in enumerate(beams):
        x, y = offsets.get(int(b), (np.nan, np.nan))
        if np.isnan(x):
            continue
        patches.append(Circle((x, y), radius))
        v = vals[k]
        colors.append(v if not np.isnan(v) else -999)

    colors = np.array(colors, dtype=float)
    mask_missing = colors < -900

    pc = PatchCollection(patches, cmap=cmap, edgecolors="0.3", linewidths=0.5)
    pc.set_clim(vmin, vmax)
    color_arr = colors.copy()
    color_arr[mask_missing] = vmin
    pc.set_array(color_arr)
    ax.add_collection(pc)

    if mask_missing.any():
        nan_patches = [p for p, m in zip(patches, mask_missing) if m]
        nan_pc = PatchCollection(
            nan_patches, facecolor="white", edgecolors="0.6",
            linewidths=0.5, hatch="//",
        )
        ax.add_collection(nan_pc)

    for k, b in enumerate(beams):
        x, y = offsets.get(int(b), (np.nan, np.nan))
        if np.isnan(x):
            continue
        v = vals[k]
        ax.text(x, y + radius * 0.25, f"B{int(b)}",
                ha="center", va="center",
                fontsize=6, fontweight="bold", color="black")
        dl_label = f"{v:.2f}" if not np.isnan(v) else "\u2014"
        ax.text(x, y - radius * 0.25, dl_label,
                ha="center", va="center",
                fontsize=5.5, fontweight="normal", color="black")

    pad = radius * 1.5
    ax.set_xlim(xs.min() - pad, xs.max() + pad)
    ax.set_ylim(ys.min() - pad, ys.max() + pad)
    ax.set_aspect("equal")
    ax.invert_xaxis()
    ax.set_xlabel("Relative RA offset (deg)")
    ax.set_ylabel("Relative Dec offset (deg)")

    sm = plt.cm.ScalarMappable(cmap=cmap, norm=plt.Normalize(vmin=vmin, vmax=vmax))
    sm.set_array([])
    cb = fig.colorbar(sm, ax=ax, fraction=0.046, pad=0.04, shrink=0.5)
    cb.set_label("dL  (%)")

    ax.set_title(
        f"{field_name}  |  ODC {odc_val}  |  {var_label}",
        fontsize=10, fontweight="bold",
    )
    fig.tight_layout()

    safe_field = field_name.replace("/", "_")
    # variant short tag: "bpcal" or "lcal"
    vtag = var_name.replace("dL_", "")
    out_path = output_dir / f"footprint_dL_{safe_field}_odc{odc_val}_{vtag}.png"
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return out_path


def plot_single_panel_qu(ds, offsets, field_name, odc_val, vtag,
                         output_dir, vmin=0, vmax=1.5):
    """
    Single split-circle Q/U panel for one (field, ODC, variant) combination.
    Outputs footprint_QU_{field}_odc{odc}_{vtag}.png.
    """
    q_var = f"dQ_{vtag}"
    u_var = f"dU_{vtag}"
    if q_var not in ds and u_var not in ds:
        return None

    beams = ds.beam.values
    xs = np.array([offsets.get(int(b), (np.nan, np.nan))[0] for b in beams])
    ys = np.array([offsets.get(int(b), (np.nan, np.nan))[1] for b in beams])

    dists = []
    for i in range(len(xs)):
        for j in range(i + 1, len(xs)):
            d = np.hypot(xs[i] - xs[j], ys[i] - ys[j])
            if d > 0:
                dists.append(d)
    radius = min(dists) / 2.0 if dists else 0.4

    q_vals = ds[q_var].sel(field=field_name, odc=odc_val).values if q_var in ds else np.full(len(beams), np.nan)
    u_vals = ds[u_var].sel(field=field_name, odc=odc_val).values if u_var in ds else np.full(len(beams), np.nan)

    if np.all(np.isnan(q_vals)) and np.all(np.isnan(u_vals)):
        return None

    cmap = plt.cm.RdYlGn_r
    norm = plt.Normalize(vmin=vmin, vmax=vmax)

    fig, ax = plt.subplots(figsize=(5.5, 5.5))

    q_wedges, q_colors = [], []
    u_wedges, u_colors = [], []
    for k, b in enumerate(beams):
        x, y = offsets.get(int(b), (np.nan, np.nan))
        if np.isnan(x):
            continue
        # Visual top-left (Q): data top-right wedge 315→135 (after x-inversion)
        q_wedges.append(Wedge((x, y), radius, 315, 135))
        q_colors.append(q_vals[k] if not np.isnan(q_vals[k]) else -999)
        # Visual bottom-right (U): data bottom-left wedge 135→315
        u_wedges.append(Wedge((x, y), radius, 135, 315))
        u_colors.append(u_vals[k] if not np.isnan(u_vals[k]) else -999)

    def _make_pc(wedges, colors):
        colors = np.array(colors, dtype=float)
        mask = colors < -900
        pc = PatchCollection(wedges, cmap=cmap, edgecolors="none")
        pc.set_norm(norm)
        arr = colors.copy()
        arr[mask] = vmin
        pc.set_array(arr)
        return pc, mask

    q_pc, q_mask = _make_pc(q_wedges, q_colors)
    u_pc, u_mask = _make_pc(u_wedges, u_colors)
    ax.add_collection(q_pc)
    ax.add_collection(u_pc)

    _d = np.sqrt(0.5)  # cos/sin of 45°
    for k, b in enumerate(beams):
        x, y = offsets.get(int(b), (np.nan, np.nan))
        if np.isnan(x):
            continue
        # Diagonal dividing line: data 315°→135° appears as visual lower-left→upper-right
        ax.plot([x + radius * _d, x - radius * _d],
                [y - radius * _d, y + radius * _d],
                color="0.35", lw=0.6, zorder=3)
        ax.add_patch(Circle((x, y), radius, fill=False, edgecolor="0.35", lw=0.6, zorder=3))

    for mask, wedges in ((q_mask, q_wedges), (u_mask, u_wedges)):
        if mask.any():
            nan_pc = PatchCollection(
                [w for w, m in zip(wedges, mask) if m],
                facecolor="white", edgecolors="0.6", linewidths=0.4, hatch="//",
            )
            ax.add_collection(nan_pc)

    for k, b in enumerate(beams):
        x, y = offsets.get(int(b), (np.nan, np.nan))
        if np.isnan(x):
            continue
        ax.text(x, y, f"B{int(b)}",
                ha="center", va="center", fontsize=6, fontweight="bold", color="black", zorder=4)
        ql = f"{q_vals[k]:.2f}" if not np.isnan(q_vals[k]) else "\u2014"
        ul = f"{u_vals[k]:.2f}" if not np.isnan(u_vals[k]) else "\u2014"
        # Q value: data top-right (= visual top-left after inversion)
        ax.text(x + radius * 0.32, y + radius * 0.32, ql,
                ha="center", va="center", fontsize=4.5, color="black", zorder=4)
        # U value: data bottom-left (= visual bottom-right after inversion)
        ax.text(x - radius * 0.32, y - radius * 0.32, ul,
                ha="center", va="center", fontsize=4.5, color="black", zorder=4)

    pad = radius * 1.5
    ax.set_xlim(xs.min() - pad, xs.max() + pad)
    ax.set_ylim(ys.min() - pad, ys.max() + pad)
    ax.set_aspect("equal")
    ax.invert_xaxis()
    ax.set_xlabel("Relative RA offset (deg)")
    ax.set_ylabel("Relative Dec offset (deg)")

    sm = plt.cm.ScalarMappable(cmap=cmap, norm=norm)
    sm.set_array([])
    cb = fig.colorbar(sm, ax=ax, fraction=0.046, pad=0.04, shrink=0.5)
    cb.set_label("|Q|/I  or  |U|/I  (%)")

    var_label = "Bandpass calibrated" if vtag == "bpcal" else "Bandpass + Leakage (on-axis) calibrated"
    ax.set_title(f"{field_name}  |  ODC {odc_val}  |  {var_label}", fontsize=10, fontweight="bold")

    # Legend: split-circle in top-left
    leg_ax = fig.add_axes([0.01, 0.84, 0.14, 0.14])
    leg_ax.set_aspect("equal")
    leg_ax.set_xlim(-1.6, 1.6)
    leg_ax.set_ylim(-1.6, 1.8)
    leg_ax.axis("off")
    # Legend: no invert_xaxis, so Q top-left = Wedge(45,225), U bottom-right = Wedge(225,405)
    _lq_fc = (*cmap(0.25)[:3], 0.45)  # lower-leakage hue, semi-transparent
    _lu_fc = (*cmap(0.75)[:3], 0.45)  # higher-leakage hue, semi-transparent
    lq = PatchCollection([Wedge((0, 0), 1, 45, 225)], facecolor=_lq_fc, edgecolors="0.4", linewidths=0.6)
    lu = PatchCollection([Wedge((0, 0), 1, 225, 405)], facecolor=_lu_fc, edgecolors="0.4", linewidths=0.6)
    leg_ax.add_collection(lq)
    leg_ax.add_collection(lu)
    _ld = np.sqrt(0.5)
    leg_ax.plot([-_ld, _ld], [-_ld, _ld], color="0.4", lw=0.8, zorder=3)
    leg_ax.add_patch(Circle((0, 0), 1, fill=False, edgecolor="0.4", lw=0.8, zorder=4))
    leg_ax.text(-0.42, 0.42, r"$|Q|/I$", ha="center", va="center", fontsize=5.5, color="0.2")
    leg_ax.text( 0.42, -0.42, r"$|U|/I$", ha="center", va="center", fontsize=5.5, color="0.2")
    leg_ax.set_title("legend", fontsize=5, color="0.4", pad=2)

    fig.tight_layout()

    safe_field = field_name.replace("/", "_")
    out_path = output_dir / f"footprint_QU_{safe_field}_odc{odc_val}_{vtag}.png"
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return out_path


def plot_field_qu(ds, offsets, field_name, output_dir, vmin=0, vmax=1.5):
    """
    Split-circle Q/U footprint plot for one reference field.

    Layout: 2 rows (bpcal, lcal) × N_odc columns.
    Each beam drawn as two wedges: visual left half = |Q|/I, visual right half = |U|/I.
    Note: ax.invert_xaxis() is applied (RA increases left), so the data-right wedge
    (270°→90°) becomes the visual-left half carrying Q, and the data-left wedge (90°→270°)
    becomes the visual-right half carrying U.
    Shared colormap and scale across both Stokes.
    """
    variants = [
        ("dQ_bpcal", "dU_bpcal", "Bandpass calibrated"),
        ("dQ_lcal",    "dU_lcal",    "Bandpass + Leakage (on-axis) calibrated"),
    ]
    odcs = ds.odc.values
    n_odc = len(odcs)

    beams = ds.beam.values
    xs = np.array([offsets.get(int(b), (np.nan, np.nan))[0] for b in beams])
    ys = np.array([offsets.get(int(b), (np.nan, np.nan))[1] for b in beams])

    dists = []
    for i in range(len(xs)):
        for j in range(i + 1, len(xs)):
            d = np.hypot(xs[i] - xs[j], ys[i] - ys[j])
            if d > 0:
                dists.append(d)
    radius = min(dists) / 2.0 if dists else 0.4

    cmap = plt.cm.RdYlGn_r
    norm = plt.Normalize(vmin=vmin, vmax=vmax)

    fig, axes = plt.subplots(
        len(variants), n_odc,
        figsize=(4.5 * n_odc, 4.5 * len(variants)),
        squeeze=False,
    )

    for row, (q_var, u_var, var_label) in enumerate(variants):
        for col, odc_val in enumerate(odcs):
            ax = axes[row, col]

            q_missing = q_var not in ds
            u_missing = u_var not in ds
            if q_missing and u_missing:
                ax.set_visible(False)
                continue

            q_vals = ds[q_var].sel(field=field_name, odc=odc_val).values if not q_missing else np.full(len(beams), np.nan)
            u_vals = ds[u_var].sel(field=field_name, odc=odc_val).values if not u_missing else np.full(len(beams), np.nan)

            q_wedges, q_colors = [], []
            u_wedges, u_colors = [], []

            for k, b in enumerate(beams):
                x, y = offsets.get(int(b), (np.nan, np.nan))
                if np.isnan(x):
                    continue
                # Visual top-left (Q): data top-right wedge 315°→135° (after x-inversion)
                q_wedges.append(Wedge((x, y), radius, 315, 135))
                q_colors.append(q_vals[k] if not np.isnan(q_vals[k]) else -999)
                # Visual bottom-right (U): data bottom-left wedge 135°→315°
                u_wedges.append(Wedge((x, y), radius, 135, 315))
                u_colors.append(u_vals[k] if not np.isnan(u_vals[k]) else -999)

            def _make_pc(wedges, colors):
                colors = np.array(colors, dtype=float)
                mask = colors < -900
                pc = PatchCollection(wedges, cmap=cmap, edgecolors="none")
                pc.set_norm(norm)
                arr = colors.copy()
                arr[mask] = vmin
                pc.set_array(arr)
                return pc, mask

            q_pc, q_mask = _make_pc(q_wedges, q_colors)
            u_pc, u_mask = _make_pc(u_wedges, u_colors)
            ax.add_collection(q_pc)
            ax.add_collection(u_pc)

            # Diagonal dividing line: data 315°→135° = visual lower-left→upper-right
            _d = np.sqrt(0.5)
            for k, b in enumerate(beams):
                x, y = offsets.get(int(b), (np.nan, np.nan))
                if np.isnan(x):
                    continue
                ax.plot([x + radius * _d, x - radius * _d],
                        [y - radius * _d, y + radius * _d],
                        color="0.35", lw=0.6, zorder=3)
                ax.add_patch(Circle((x, y), radius,
                             fill=False, edgecolor="0.35", lw=0.6, zorder=3))

            # Hatching for missing data
            for mask, wedges in ((q_mask, q_wedges), (u_mask, u_wedges)):
                if mask.any():
                    nan_pc = PatchCollection(
                        [w for w, m in zip(wedges, mask) if m],
                        facecolor="white", edgecolors="0.6",
                        linewidths=0.4, hatch="//",
                    )
                    ax.add_collection(nan_pc)

            # Labels: beam number centre; Q in data top-right (visual top-left); U in data bottom-left (visual bottom-right)
            for k, b in enumerate(beams):
                x, y = offsets.get(int(b), (np.nan, np.nan))
                if np.isnan(x):
                    continue
                ax.text(x, y, f"B{int(b)}",
                        ha="center", va="center",
                        fontsize=5, fontweight="bold", color="black", zorder=4)
                ql = f"{q_vals[k]:.2f}" if not np.isnan(q_vals[k]) else "—"
                ul = f"{u_vals[k]:.2f}" if not np.isnan(u_vals[k]) else "—"
                ax.text(x + radius * 0.32, y + radius * 0.32, ql,
                        ha="center", va="center",
                        fontsize=4.5, color="black", zorder=4)
                ax.text(x - radius * 0.32, y - radius * 0.32, ul,
                        ha="center", va="center",
                        fontsize=4.5, color="black", zorder=4)

            pad = radius * 1.5
            ax.set_xlim(xs.min() - pad, xs.max() + pad)
            ax.set_ylim(ys.min() - pad, ys.max() + pad)
            ax.set_aspect("equal")
            ax.invert_xaxis()
            ax.set_xlabel("Relative RA offset (deg)")
            ax.set_ylabel("Relative Dec offset (deg)")

            if row == 0:
                ax.set_title(f"ODC {odc_val}", fontsize=11, fontweight="bold")
            if col == 0:
                ax.annotate(
                    var_label, xy=(-0.18, 0.5), xycoords="axes fraction",
                    rotation=90, va="center", ha="center",
                    fontsize=10, fontweight="bold",
                )

    # Shared colourbar
    cbar_ax = fig.add_axes([0.92, 0.15, 0.015, 0.7])
    sm = plt.cm.ScalarMappable(cmap=cmap, norm=norm)
    sm.set_array([])
    cb = fig.colorbar(sm, cax=cbar_ax)
    cb.set_label("|Q|/I  or  |U|/I  (%)", fontsize=10)

    # Legend: split circle — top-left of figure
    leg_ax = fig.add_axes([0.01, 0.84, 0.08, 0.08])
    leg_ax.set_aspect("equal")
    leg_ax.set_xlim(-1.6, 1.6)
    leg_ax.set_ylim(-1.6, 1.8)
    leg_ax.axis("off")
    # Legend: no invert_xaxis, so Q top-left = Wedge(45,225), U bottom-right = Wedge(225,405)
    _lq_fc = (*cmap(0.25)[:3], 0.45)  # lower-leakage hue, semi-transparent
    _lu_fc = (*cmap(0.75)[:3], 0.45)  # higher-leakage hue, semi-transparent
    lq = PatchCollection([Wedge((0, 0), 1, 45, 225)], facecolor=_lq_fc, edgecolors="0.4", linewidths=0.6)
    lu = PatchCollection([Wedge((0, 0), 1, 225, 405)], facecolor=_lu_fc, edgecolors="0.4", linewidths=0.6)
    leg_ax.add_collection(lq)
    leg_ax.add_collection(lu)
    _ld = np.sqrt(0.5)
    leg_ax.plot([-_ld, _ld], [-_ld, _ld], color="0.4", lw=0.8, zorder=3)
    leg_ax.add_patch(Circle((0, 0), 1, fill=False, edgecolor="0.4", lw=0.8, zorder=4))
    leg_ax.text(-0.42, 0.42, r"$|Q|/I$", ha="center", va="center", fontsize=5.5, color="0.2")
    leg_ax.text( 0.42, -0.42, r"$|U|/I$", ha="center", va="center", fontsize=5.5, color="0.2")
    leg_ax.set_title("legend", fontsize=5, color="0.4", pad=2)

    fig.suptitle(
        f"Q/U Leakage — {field_name}",
        fontsize=13, fontweight="bold", y=0.98,
    )
    fig.subplots_adjust(left=0.08, right=0.90, top=0.93, bottom=0.06, wspace=0.25, hspace=0.22)

    safe_name = field_name.replace("/", "_")
    out_path = output_dir / f"footprint_QU_{safe_name}.png"
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  Wrote {out_path}")
    return out_path


def plot_field(ds, offsets, field_name, output_dir, vmin=None, vmax=None):
    """
    Plot one figure for a given reference field.

    Layout: 2 rows (Bandpass calibrated, Bandpass+Lcal) × N_odc columns.
    """
    variants = [
        ("dL_bpcal", "Bandpass calibrated"),
        ("dL_lcal", "Bandpass + Leakage (on-axis) calibrated"),
    ]
    odcs = ds.odc.values
    n_odc = len(odcs)

    # Beam positions
    beams = ds.beam.values
    xs = np.array([offsets.get(int(b), (np.nan, np.nan))[0] for b in beams])
    ys = np.array([offsets.get(int(b), (np.nan, np.nan))[1] for b in beams])

    # Circle radius = half the minimum beam separation
    dists = []
    for i in range(len(xs)):
        for j in range(i + 1, len(xs)):
            d = np.hypot(xs[i] - xs[j], ys[i] - ys[j])
            if d > 0:
                dists.append(d)
    radius = min(dists) / 2.0 if dists else 0.4

    # Auto colour range across both variants for this field
    if vmin is None or vmax is None:
        all_vals = []
        for var_name, _ in variants:
            if var_name in ds:
                sl = ds[var_name].sel(field=field_name)
                all_vals.append(sl.values[~np.isnan(sl.values)])
        if all_vals:
            combined = np.concatenate(all_vals)
            if vmin is None:
                vmin = float(np.nanmin(combined))
            if vmax is None:
                vmax = float(np.nanmax(combined))
        else:
            vmin, vmax = 0, 1

    fig, axes = plt.subplots(
        len(variants), n_odc,
        figsize=(4.5 * n_odc, 4.5 * len(variants)),
        squeeze=False,
    )

    cmap = plt.cm.RdYlGn_r  # red=high leakage, green=low

    for row, (var_name, var_label) in enumerate(variants):
        for col, odc_val in enumerate(odcs):
            ax = axes[row, col]

            if var_name not in ds:
                ax.set_visible(False)
                continue

            sl = ds[var_name].sel(field=field_name, odc=odc_val)
            vals = sl.values  # shape (n_beam,)

            patches = []
            colors = []
            for k, b in enumerate(beams):
                x, y = offsets.get(int(b), (np.nan, np.nan))
                if np.isnan(x):
                    continue
                patches.append(Circle((x, y), radius))
                v = vals[k]
                colors.append(v if not np.isnan(v) else -999)

            colors = np.array(colors, dtype=float)
            mask_missing = colors < -900

            pc = PatchCollection(patches, cmap=cmap, edgecolors="0.3", linewidths=0.5)
            pc.set_clim(vmin, vmax)
            color_arr = colors.copy()
            color_arr[mask_missing] = vmin  # will be overdrawn
            pc.set_array(color_arr)
            ax.add_collection(pc)

            # Overlay hatching for NaN cells
            if mask_missing.any():
                nan_patches = [p for p, m in zip(patches, mask_missing) if m]
                nan_pc = PatchCollection(
                    nan_patches, facecolor="white", edgecolors="0.6",
                    linewidths=0.5, hatch="//",
                )
                ax.add_collection(nan_pc)

            # Beam labels: "B<n>" (bold, centre) + dL value (regular, below)
            for k, b in enumerate(beams):
                x, y = offsets.get(int(b), (np.nan, np.nan))
                if np.isnan(x):
                    continue
                v = vals[k]
                # beam index — bold, centred slightly above middle
                ax.text(x, y + radius * 0.25, f"B{int(b)}",
                        ha="center", va="center",
                        fontsize=5, fontweight="bold", color="black")
                # dL value — regular weight, smaller, below middle
                dl_label = f"{v:.2f}" if not np.isnan(v) else "—"
                ax.text(x, y - radius * 0.25, dl_label,
                        ha="center", va="center",
                        fontsize=4.5, fontweight="normal", color="black")

            pad = radius * 1.5
            ax.set_xlim(xs.min() - pad, xs.max() + pad)
            ax.set_ylim(ys.min() - pad, ys.max() + pad)
            ax.set_aspect("equal")
            ax.invert_xaxis()  # RA increases to the left
            ax.set_xlabel("Relative RA offset (deg)")
            ax.set_ylabel("Relative Dec offset (deg)")

            if row == 0:
                ax.set_title(f"ODC {odc_val}", fontsize=11, fontweight="bold")
            if col == 0:
                ax.annotate(
                    var_label, xy=(-0.18, 0.5), xycoords="axes fraction",
                    rotation=90, va="center", ha="center",
                    fontsize=10, fontweight="bold",
                )

    # Shared colourbar
    cbar_ax = fig.add_axes([0.92, 0.15, 0.015, 0.7])
    sm = plt.cm.ScalarMappable(cmap=cmap, norm=plt.Normalize(vmin=vmin, vmax=vmax))
    sm.set_array([])
    cb = fig.colorbar(sm, cax=cbar_ax)
    cb.set_label("dL  (%)", fontsize=10)

    fig.suptitle(
        f"Residual On-axis Leakage — {field_name}",
        fontsize=13, fontweight="bold", y=0.98,
    )
    fig.subplots_adjust(left=0.08, right=0.90, top=0.93, bottom=0.06, wspace=0.25, hspace=0.22)

    safe_name = field_name.replace("/", "_")
    out_path = output_dir / f"footprint_dL_{safe_name}.png"
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  Wrote {out_path}")
    return out_path


def main():
    parser = argparse.ArgumentParser(description="Plot leakage cube as footprint heatmaps")
    parser.add_argument(
        "--data-root",
        default=str(Path.home() / "DATA" / "reffield-average"),
        help="Top-level data directory",
    )
    parser.add_argument(
        "--field",
        default=None,
        help="Plot only this reference field (default: all)",
    )
    args = parser.parse_args()

    data_root = Path(args.data_root)
    cube_path = data_root / "phase2" / "leakage_cube.nc"
    if not cube_path.exists():
        raise FileNotFoundError(f"Missing: {cube_path}  — run build_leakage_cube.py first")

    ds = xr.open_dataset(cube_path)

    # ── Validate all footprints and get consensus offsets ───────────────
    offsets = load_and_validate_footprint(data_root)
    print(f"Using {len(offsets)} beam offsets from validated footprints")

    # ── Output directory ────────────────────────────────────────────────
    plot_dir = data_root / "phase3" / "plots"
    plot_dir.mkdir(parents=True, exist_ok=True)

    # ── Plot ────────────────────────────────────────────────────────────
    variants_single = [
        ("dL_bpcal", "Bandpass calibrated"),
        ("dL_lcal", "Bandpass + Leakage (on-axis) calibrated"),
    ]
    fields = [args.field] if args.field else list(ds.field.values)
    for field_name in fields:
        print(f"Plotting {field_name} ...")
        plot_field(ds, offsets, field_name, plot_dir, vmin=0, vmax=1.5)
        plot_field_qu(ds, offsets, field_name, plot_dir, vmin=0, vmax=1.5)
        # Individual single-panel plots (dL and QU per odc/variant)
        for odc_val in ds.odc.values:
            for var_name, var_label in variants_single:
                vtag = var_name.replace("dL_", "")
                p = plot_single_panel(
                    ds, offsets, field_name, odc_val, var_name, var_label,
                    plot_dir, vmin=0, vmax=1.5,
                )
                if p:
                    print(f"    {p.name}")
                pqu = plot_single_panel_qu(
                    ds, offsets, field_name, odc_val, vtag,
                    plot_dir, vmin=0, vmax=1.5,
                )
                if pqu:
                    print(f"    {pqu.name}")


if __name__ == "__main__":
    main()
