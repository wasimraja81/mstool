#!/usr/bin/env python3
"""
plot_dQ_vs_beam.py
──────────────────
Plot signed dQ/I (%) — and optionally dU/I (%) — vs beam number for each
reference field, using the leakage_master_table.csv produced by
build_phase1_master_table.py.

Layout
------
  • One subplot per ref_fieldname (drawn from the manifest-selected rows)
  • Lines coloured by ODC weight
  • Marker shape cycles over SB_REF observations of the same field
  • Separate figures for 'regular' and 'lcal' variants, or both

CLI options deliberately mirror build_phase1_master_table.py so that the same
manifest selection (--start-index, --end-index, --exclude-indices) controls
which observations are plotted, consistent with the rest of the pipeline.

Usage
-----
  # Default: indices 14-49, excl 24-29 (same as build_phase1_master_table.py)
  python plot_dQ_vs_beam.py

  # Regular variant only, interactive display
  python plot_dQ_vs_beam.py --variant regular --show

  # Also plot dU alongside dQ
  python plot_dQ_vs_beam.py --dU

  # Override index range (same pattern as build_phase1_master_table.py)
  python plot_dQ_vs_beam.py --start-index 14 --end-index 49 --exclude-indices "24-29"
"""

import argparse
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.cm as cm
import matplotlib.lines as mlines
import numpy as np
import pandas as pd

# ── Import manifest infrastructure from build_phase1_master_table ───────────
_scripts_dir = Path(__file__).resolve().parent
sys.path.insert(0, str(_scripts_dir))
from build_phase1_master_table import (
    parse_exclude_indices,
    is_excluded,
    parse_manifest_rows,
)

MARKERS = ["o", "s", "^", "D", "v", "P", "X", "*", "h", "+"]
MANIFEST_DEFAULT = "projects/calibration-updates-2026/manifests/sb_manifest_reffield_average.txt"


def make_figure(df_field: pd.DataFrame, field: str, variant: str, quantity: str,
                ylabel: str, output_dir: Path, show: bool):
    """Generate one figure (single axes) for a single ref_fieldname."""
    odcs = sorted(df_field["odc_weight"].unique())
    odc_colours = {odc: cm.tab10(i / max(len(odcs) - 1, 1)) for i, odc in enumerate(odcs)}

    sbs = sorted(df_field["sb_ref"].unique())
    sb_markers = {sb: MARKERS[i % len(MARKERS)] for i, sb in enumerate(sbs)}

    fig, ax = plt.subplots(figsize=(9, 5))
    fig.suptitle(f"{field}  —  signed {ylabel} vs beam  —  variant: {variant}",
                 fontsize=12, y=1.01)

    for odc in odcs:
        colour = odc_colours[odc]
        for sb in sbs:
            row = df_field[(df_field["odc_weight"] == odc) & (df_field["sb_ref"] == sb)
                           ].sort_values("beam")
            if row.empty:
                continue
            ax.plot(
                row["beam"],
                row[quantity],
                color=colour,
                marker=sb_markers[sb],
                markersize=5,
                linewidth=1.2,
                alpha=0.85,
            )

    ax.axhline(0, color="black", linewidth=0.6, linestyle="--", alpha=0.4)
    ax.set_xlabel("Beam", fontsize=9)
    ax.set_ylabel(f"{ylabel} signed (%)", fontsize=9)
    ax.tick_params(labelsize=8)
    ax.set_xticks(range(0, 36, 3))
    ax.grid(True, linewidth=0.4, alpha=0.4)

    # ── Legends ──────────────────────────────────────────────────────────────
    odc_handles = [
        mlines.Line2D([], [], color=odc_colours[odc], linewidth=2, label=f"ODC {odc}")
        for odc in odcs
    ]
    sb_handles = [
        mlines.Line2D([], [], color="grey",
                      marker=sb_markers[sb], markersize=6, linewidth=0, label=f"SB {sb}")
        for sb in sbs
    ]
    ax.legend(handles=odc_handles + sb_handles, title="ODC / SB_REF",
              title_fontsize=8, fontsize=7, framealpha=0.8,
              loc="upper right", ncol=2)

    plt.tight_layout()
    qty_tag   = quantity.replace("leak_", "").replace("_over_i_signed_pct", "")
    field_tag = field.replace("/", "-")
    out_path  = output_dir / f"{qty_tag}_vs_beam_{field_tag}_{variant}.png"
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    print(f"Saved: {out_path}")
    if show:
        plt.show()
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser(
        description="Plot signed dQ/I (and optionally dU/I) vs beam per reference field",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    # ── Paths — same conventions as build_phase1_master_table.py ─────────────
    parser.add_argument(
        "--manifest",
        default=MANIFEST_DEFAULT,
        help="Manifest file (used to resolve which SB_REF observations to include).",
    )
    parser.add_argument(
        "--data-root",
        default=str(Path.home() / "DATA" / "reffield-average"),
        help="Top-level data directory (same as --local-base in phase-1 script).",
    )
    parser.add_argument(
        "--master-csv",
        default=None,
        help="Explicit path to leakage_master_table.csv "
             "(defaults to <data-root>/leakage_master_table.csv).",
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        help="Output directory for PNGs (defaults to <data-root>/phase3/plots).",
    )

    # ── Manifest row selection — identical to build_phase1_master_table.py ────
    parser.add_argument("--start-index", type=int, default=14,
                        help="First manifest row index (0-based) to include.")
    parser.add_argument("--end-index",   type=int, default=49,
                        help="Last manifest row index (inclusive) to include.")
    parser.add_argument("--exclude-indices", default="24-29",
                        help="Comma-separated indices/ranges to exclude (e.g. '24-29,31').")

    # ── Plot options ──────────────────────────────────────────────────────────
    parser.add_argument(
        "--variant", choices=["regular", "lcal", "both"], default="both",
        help="Calibration variant(s) to plot.",
    )
    parser.add_argument(
        "--dU", action="store_true",
        help="Also produce a matching figure for signed dU/I.",
    )
    parser.add_argument(
        "--fields", default=None,
        help="Comma-separated ref_fieldname values to include (e.g. 'REF_1324-28,REF_0324-28'). "
             "Case-insensitive partial match: '1324-28' matches 'REF_1324-28'. "
             "Omit to plot all fields selected by the manifest.",
    )
    parser.add_argument("--show", action="store_true",
                        help="Display plots interactively after saving.")

    args = parser.parse_args()

    data_root  = Path(args.data_root)
    csv_path   = Path(args.master_csv) if args.master_csv else data_root / "leakage_master_table.csv"
    output_dir = Path(args.output_dir) if args.output_dir else data_root / "phase3" / "plots"
    output_dir.mkdir(parents=True, exist_ok=True)

    # ── Resolve manifest-selected sb_ref set ─────────────────────────────────
    manifest_path = Path(args.manifest)
    if not manifest_path.is_absolute():
        manifest_path = (_scripts_dir / ".." / ".." / ".." / args.manifest).resolve()

    selected_sbrefs = None
    manifest_fields = None  # ordered unique field names from manifest
    if manifest_path.exists():
        exclude_ranges = parse_exclude_indices(args.exclude_indices)
        rows = parse_manifest_rows(manifest_path, args.start_index, args.end_index, exclude_ranges)
        selected_sbrefs = {int(r["sb_ref"]) for r in rows}
        # preserve first-appearance order of field names across manifest rows
        seen = {}
        for r in rows:
            fn = r.get("ref_fieldname", "")
            if fn and fn not in seen:
                seen[fn] = True
        manifest_fields = list(seen.keys())
        print(f"Manifest {manifest_path.name}: {len(selected_sbrefs)} SB_REFs, "
              f"{len(manifest_fields)} unique fields "
              f"(indices {args.start_index}–{args.end_index}, excl {args.exclude_indices!r})")
    else:
        print(f"Warning: manifest not found at {manifest_path} — deriving fields from CSV.")

    # ── Load and filter master CSV ────────────────────────────────────────────
    df = pd.read_csv(csv_path)
    print(f"Loaded {len(df)} rows from {csv_path}")

    if selected_sbrefs is not None:
        df = df[df["sb_ref"].isin(selected_sbrefs)]
        print(f"After manifest filter: {len(df)} rows ({df['sb_ref'].nunique()} SB_REFs)")

    # ── Determine which fields to iterate over ────────────────────────────────
    # Default: unique field names from manifest rows (ordered); no giant consolidated plot.
    if args.fields:
        tokens = [f.strip() for f in args.fields.split(",") if f.strip()]
        def _field_match(name):
            name_l = str(name).lower()
            return any(t.lower() in name_l for t in tokens)
        if manifest_fields is not None:
            fields_to_plot = [f for f in manifest_fields if _field_match(f)]
        else:
            fields_to_plot = sorted(n for n in df["ref_fieldname"].unique() if _field_match(n))
        print(f"--fields filter ({args.fields!r}) → {fields_to_plot}")
    else:
        fields_to_plot = manifest_fields if manifest_fields is not None \
            else sorted(df["ref_fieldname"].unique())

    if not fields_to_plot:
        print("No matching fields — nothing to plot.")
        return

    variants  = ["regular", "lcal"] if args.variant == "both" else [args.variant]
    quantities = [("leak_q_over_i_signed_pct", "dQ/I")]
    if args.dU:
        quantities.append(("leak_u_over_i_signed_pct", "dU/I"))

    for field in fields_to_plot:
        df_field = df[df["ref_fieldname"] == field]
        if df_field.empty:
            print(f"No CSV rows for {field}, skipping.")
            continue
        for v in variants:
            sub = df_field[df_field["variant"] == v]
            if sub.empty:
                print(f"  No rows for {field} / variant={v}, skipping.")
                continue
            for col, label in quantities:
                make_figure(sub, field, v, col, label, output_dir, args.show)


if __name__ == "__main__":
    main()
