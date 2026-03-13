#!/usr/bin/env python3
"""
Build an xarray Dataset (saved as NetCDF4) representing the 3-D leakage cube.

Dimensions
----------
beam     : 0-35   (PAF beam index)
field    : string (reference calibrator field name, e.g. REF_0236-28)
odc      : int    (ODC WEIGHTS ID, e.g. 5229)

Variables (per variant)
-----------------------
dL_regular   : median_l_over_i for variant=regular   [beam, field, odc]
dL_lcal      : median_l_over_i for variant=lcal      [beam, field, odc]
p90_regular  : p90_l_over_i    for variant=regular    [beam, field, odc]
p90_lcal     : p90_l_over_i    for variant=lcal       [beam, field, odc]
dQ_regular   : median_q_over_i for variant=regular   [beam, field, odc]
dQ_lcal      : median_q_over_i for variant=lcal      [beam, field, odc]
dU_regular   : median_u_over_i for variant=regular   [beam, field, odc]
dU_lcal      : median_u_over_i for variant=lcal      [beam, field, odc]
nsb_regular  : count_sb_ref    for variant=regular    [beam, field, odc]
nsb_lcal     : count_sb_ref    for variant=lcal       [beam, field, odc]

Input
-----
beam_x_field_at_fixed_odc.csv  (Phase-2 output)

Usage
-----
    python build_leakage_cube.py [--data-root ~/DATA/reffield-average]

Output
------
    <data-root>/phase2/leakage_cube.nc
"""

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr


def main():
    parser = argparse.ArgumentParser(description="Build 3-D leakage cube as NetCDF4")
    parser.add_argument(
        "--data-root",
        default=str(Path.home() / "DATA" / "reffield-average"),
        help="Top-level data directory (default: ~/DATA/reffield-average)",
    )
    args = parser.parse_args()

    data_root = Path(args.data_root)
    phase2 = data_root / "phase2"

    # ── Read the beam-level CSV ─────────────────────────────────────────
    csv_path = phase2 / "beam_x_field_at_fixed_odc.csv"
    if not csv_path.exists():
        raise FileNotFoundError(f"Missing: {csv_path}")

    df = pd.read_csv(csv_path)
    print(f"Read {len(df)} rows from {csv_path}")

    # ── Coordinate arrays ───────────────────────────────────────────────
    beams = np.sort(df["beam"].unique())
    fields = np.sort(df["ref_fieldname"].unique())
    odcs = np.sort(df["odc_weight"].unique())
    variants = ["regular", "lcal"]

    nb, nf, no = len(beams), len(fields), len(odcs)
    print(f"Cube shape: beam={nb} × field={nf} × odc={no} × variant={len(variants)}")

    # ── Build arrays ────────────────────────────────────────────────────
    # Map coordinates to indices for fast placement
    beam_idx = {b: i for i, b in enumerate(beams)}
    field_idx = {f: i for i, f in enumerate(fields)}
    odc_idx = {o: i for i, o in enumerate(odcs)}

    # Initialise with NaN
    arrays = {}
    for var in variants:
        for col, label in [
            ("median_l_over_i", "dL"),
            ("p90_l_over_i", "p90"),
            ("median_q_over_i", "dQ"),
            ("median_u_over_i", "dU"),
            ("count_sb_ref", "nsb"),
        ]:
            arrays[f"{label}_{var}"] = np.full((nb, nf, no), np.nan)

    # Fill from dataframe
    for _, row in df.iterrows():
        bi = beam_idx[row["beam"]]
        fi = field_idx[row["ref_fieldname"]]
        oi = odc_idx[row["odc_weight"]]
        var = row["variant"]
        if var not in variants:
            continue
        arrays[f"dL_{var}"][bi, fi, oi] = row["median_l_over_i"]
        arrays[f"p90_{var}"][bi, fi, oi] = row["p90_l_over_i"]
        if "median_q_over_i" in row and pd.notna(row["median_q_over_i"]):
            arrays[f"dQ_{var}"][bi, fi, oi] = row["median_q_over_i"]
        if "median_u_over_i" in row and pd.notna(row["median_u_over_i"]):
            arrays[f"dU_{var}"][bi, fi, oi] = row["median_u_over_i"]
        arrays[f"nsb_{var}"][bi, fi, oi] = row["count_sb_ref"]

    # ── Build xarray Dataset ────────────────────────────────────────────
    coords = {
        "beam": ("beam", beams),
        "field": ("field", fields),
        "odc": ("odc", odcs),
    }
    dims = ("beam", "field", "odc")

    data_vars = {}
    long_names = {
        "dL": "Percentage linear polarisation leakage, dL = 100 × L/I",
        "p90": "90th percentile of dL across SB_REF samples",
        "dQ": "Percentage Stokes Q leakage, |Q|/I × 100 (median across valid channels)",
        "dU": "Percentage Stokes U leakage, |U|/I × 100 (median across valid channels)",
        "nsb": "Number of independent SB_REF observations",
    }
    units = {"dL": "%", "p90": "%", "dQ": "%", "dU": "%", "nsb": "count"}
    variant_labels = {
        "regular": "Bandpass calibrated",
        "lcal": "Bandpass + Leakage (on-axis) calibrated",
    }

    for key, arr in arrays.items():
        # key is e.g. "dL_regular"
        base, var = key.rsplit("_", 1)
        attrs = {
            "long_name": f"{long_names[base]} [{variant_labels[var]}]",
            "units": units[base],
            "variant": var,
        }
        data_vars[key] = xr.Variable(dims, arr, attrs=attrs)

    ds = xr.Dataset(data_vars, coords=coords)
    ds.attrs["title"] = "Residual On-axis Leakage Cube"
    ds.attrs["description"] = (
        "3-D cube of percentage linear polarisation leakage (dL) "
        "indexed by beam, reference field, and ODC weight. "
        "dL = 100 × L/I where L is linear polarisation intensity "
        "and I is Stokes I total intensity."
    )
    ds.attrs["source"] = str(csv_path)
    ds.attrs["conventions"] = "CF-1.8"

    # ── Report ──────────────────────────────────────────────────────────
    print()
    print(ds)
    print()

    # Quick sanity: NaN counts
    for name in ds.data_vars:
        total = ds[name].size
        if total == 0:
            print(f"  {name}: empty (0 cells)")
            continue
        nans = int(np.isnan(ds[name].values).sum())
        print(f"  {name}: {total} cells, {nans} NaN ({100*nans/total:.1f}%)")

    # ── Write NetCDF ────────────────────────────────────────────────────
    out_path = phase2 / "leakage_cube.nc"
    ds.to_netcdf(out_path, format="NETCDF4")
    print(f"\nWrote {out_path}  ({out_path.stat().st_size / 1024:.1f} KB)")


if __name__ == "__main__":
    main()
