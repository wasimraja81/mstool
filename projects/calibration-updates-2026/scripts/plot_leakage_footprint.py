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
from matplotlib.patches import Circle


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
    # variant short tag: "regular" or "lcal"
    vtag = var_name.replace("dL_", "")
    out_path = output_dir / f"footprint_dL_{safe_field}_odc{odc_val}_{vtag}.png"
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return out_path


def plot_field(ds, offsets, field_name, output_dir, vmin=None, vmax=None):
    """
    Plot one figure for a given reference field.

    Layout: 2 rows (Bandpass calibrated, Bandpass+Lcal) × N_odc columns.
    """
    variants = [
        ("dL_regular", "Bandpass calibrated"),
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
        ("dL_regular", "Bandpass calibrated"),
        ("dL_lcal", "Bandpass + Leakage (on-axis) calibrated"),
    ]
    fields = [args.field] if args.field else list(ds.field.values)
    for field_name in fields:
        print(f"Plotting {field_name} ...")
        plot_field(ds, offsets, field_name, plot_dir, vmin=0, vmax=1.5)
        # Individual single-panel plots
        for odc_val in ds.odc.values:
            for var_name, var_label in variants_single:
                p = plot_single_panel(
                    ds, offsets, field_name, odc_val, var_name, var_label,
                    plot_dir, vmin=0, vmax=1.5,
                )
                if p:
                    print(f"    {p.name}")


if __name__ == "__main__":
    main()
