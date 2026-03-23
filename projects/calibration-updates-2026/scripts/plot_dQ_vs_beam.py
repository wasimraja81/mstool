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
  • Separate figures for 'bpcal' and 'lcal' variants, or both

CLI options deliberately mirror build_phase1_master_table.py so that the same
manifest selection (--start-index, --end-index, --exclude-indices) controls
which observations are plotted, consistent with the rest of the pipeline.

Usage
-----
  # Default: indices 14-49, excl 24-29 (same as build_phase1_master_table.py)
  python plot_dQ_vs_beam.py

  # bpcal variant only, interactive display
  python plot_dQ_vs_beam.py --variant bpcal --show

  # Also plot dU alongside dQ
  python plot_dQ_vs_beam.py --dU

  # Override index range (same pattern as build_phase1_master_table.py)
  python plot_dQ_vs_beam.py --start-index 14 --end-index 49 --exclude-indices "24-29"
"""

import argparse
import datetime
import sys
from pathlib import Path
from typing import Optional

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
                ylabel: str, output_dir: Path, show: bool, ylim: Optional[float] = 5.0,
                mean_per_beam: Optional[pd.Series] = None):
    """Generate one figure (single axes) for a single ref_fieldname."""
    odcs = sorted(df_field["odc_weight"].unique())
    odc_colours = {odc: cm.tab10(i / max(len(odcs) - 1, 1)) for i, odc in enumerate(odcs)}

    sbs = sorted(df_field["sb_ref"].unique())
    sb_markers = {sb: MARKERS[i % len(MARKERS)] for i, sb in enumerate(sbs)}

    fig, ax = plt.subplots(figsize=(9, 5))
    fig.suptitle(f"{field}  —  {ylabel} signed (%) vs beam  —  variant: {variant}",
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
                markersize=4,
                linewidth=0.9,
                alpha=0.75,
                zorder=2,
            )

    # ── Mean line across all observations (drawn on top of individual lines) ─
    if mean_per_beam is not None and not mean_per_beam.empty:
        mx = mean_per_beam.sort_index()
        ax.fill_between(mx.index, mx.values, 0,
                        where=(mx.values >= 0), alpha=0.07, color="tomato", zorder=3)
        ax.fill_between(mx.index, mx.values, 0,
                        where=(mx.values < 0),  alpha=0.07, color="steelblue", zorder=3)
        ax.plot(mx.index, mx.values,
                color="black", linewidth=2.0, linestyle="-",
                marker="o", markersize=4, zorder=5)

    ax.axhline(0, color="black", linewidth=0.6, linestyle="--", alpha=0.4)
    if ylim is not None:
        data_extreme = df_field[quantity].abs().max()
        effective_ylim = max(ylim, data_extreme * 1.1)
        ax.set_ylim(-effective_ylim, effective_ylim)
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
    mean_handle = (
        [mlines.Line2D([], [], color="black", linewidth=2.0, linestyle="-",
                       marker="o", markersize=4, label="Mean (all obs)")]
        if mean_per_beam is not None and not mean_per_beam.empty else []
    )
    ax.legend(handles=mean_handle + odc_handles + sb_handles, title="ODC / SB_REF",
              title_fontsize=8, fontsize=7, framealpha=0.8,
              loc="upper right", ncol=2)

    plt.tight_layout()
    qty_tag   = "d" + quantity.replace("leak_", "").replace("_over_i_signed_pct", "").upper()
    field_tag = field.replace("/", "-")
    out_path  = output_dir / f"{qty_tag}_vs_beam_{field_tag}_{variant}.png"
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    print(f"Saved: {out_path}")
    if show:
        plt.show()
    plt.close(fig)


def write_correction_table(
        df: pd.DataFrame,
        fields: list,
        variants: list,
        has_dU: bool,
        output_dir: Path,
        meta: dict,
) -> None:
    """Write a human-readable ASCII lookup table of mean dQ/dU correction
    factors per beam, per variant, per reference field.

    The file is written to <output_dir>/dq_du_correction_factors.txt.
    Columns are fixed-width so the file reads cleanly with column(1) or grep.
    """
    dq_col = "leak_q_over_i_signed_pct"
    du_col = "leak_u_over_i_signed_pct"

    lines = []
    lines.append("# dQ/dU per-beam mean correction factors")
    lines.append(f"# Generated  : {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append(f"# Source CSV : {meta['csv_path']}")
    lines.append(f"# Selection  : manifest indices {meta['start_index']}–{meta['end_index']},"
                 f" excl {meta['exclude_indices']!r}")
    lines.append(f"# SB_REFs    : {meta['n_sbrefs']} contributing observations")
    lines.append(f"# Ref WS     : {meta.get('ref_ws', 'N/A')}  (weights.ref_ws, holography SB)")
    lines.append(f"# Footprint  : {meta.get('footprint_name', 'unknown')}")
    lines.append(f"# Centre Freq: {meta.get('centre_freq_mhz', 'N/A')} MHz")
    lines.append(f"# Pitch      : {meta.get('footprint_pitch_deg', 'N/A')} deg")
    lines.append(f"# Rotation   : {meta.get('footprint_rota_deg', 'N/A')} deg")
    lines.append(f"# Pol Axis   : {meta.get('pol_axis_deg', 'N/A')} deg (pa_fixed)")
    lines.append("#")
    lines.append("# Lookup usage:")
    lines.append("#   grep 'REF_1324-28.*bpcal.*  12 ' dq_du_correction_factors.txt")
    lines.append("#")
    lines.append("# Columns:")
    lines.append("#   field       reference field name")
    lines.append("#   ref_ws      holography solution (weights.ref_ws); use as merge key when appending manifests")
    lines.append("#   footprint   beam footprint name (from schedblock metadata)")
    lines.append("#   freq_MHz    beamformer centre frequency (MHz)")
    lines.append("#   pitch_deg   beam footprint pitch (degrees)")
    lines.append("#   rot_deg     footprint rotation angle (degrees)")
    lines.append("#   pol_deg     polarisation axis angle (degrees, pa_fixed)")
    lines.append("#   variant     calibration variant  (bpcal | lcal)")
    lines.append("#   beam        beam index  (0–35)")
    lines.append("#   mean_dQ     mean signed dQ/I (%) across all SB_REF × ODC observations")
    lines.append("#   std_dQ      standard deviation of dQ/I (%)")
    if has_dU:
        lines.append("#   mean_dU     mean signed dU/I (%) across all SB_REF × ODC observations")
        lines.append("#   std_dU      standard deviation of dU/I (%)")
    lines.append("#   n_obs       number of (SB_REF, ODC) data rows for this beam")
    lines.append("#")

    fp_col = meta.get('footprint_name', 'unknown')

    # Pre-format obs-metadata values for fixed-width columns
    def _fmt(val, fmt=".1f"):
        if val is None:
            return "N/A"
        try:
            return format(val, fmt)
        except (TypeError, ValueError):
            return str(val)

    freq_s   = _fmt(meta.get("centre_freq_mhz"),     ".1f")
    pitch_s  = _fmt(meta.get("footprint_pitch_deg"), ".4f")
    rot_s    = _fmt(meta.get("footprint_rota_deg"),  ".1f")
    pol_s    = _fmt(meta.get("pol_axis_deg"),         ".1f")
    ref_ws_s = str(int(meta["ref_ws"])) if meta.get("ref_ws") is not None else "N/A"

    if has_dU:
        hdr = (f"{'field':<24}  {'ref_ws':>6}  {'footprint':<16}  {'freq_MHz':>8}  "
               f"{'pitch_deg':>9}  {'rot_deg':>7}  {'pol_deg':>7}  {'variant':<8}  {'beam':>4}  "
               f"{'mean_dQ':>9}  {'std_dQ':>8}  "
               f"{'mean_dU':>9}  {'std_dU':>8}  {'n_obs':>5}")
    else:
        hdr = (f"{'field':<24}  {'ref_ws':>6}  {'footprint':<16}  {'freq_MHz':>8}  "
               f"{'pitch_deg':>9}  {'rot_deg':>7}  {'pol_deg':>7}  {'variant':<8}  {'beam':>4}  "
               f"{'mean_dQ':>9}  {'std_dQ':>8}  {'n_obs':>5}")
    lines.append(hdr)
    lines.append("-" * len(hdr))

    for field in fields:
        df_f = df[df["ref_fieldname"] == field]
        if df_f.empty:
            continue
        for v in variants:
            sub = df_f[df_f["variant"] == v]
            if sub.empty:
                continue
            grp      = sub.groupby("beam")
            mean_dq  = grp[dq_col].mean()
            std_dq   = grp[dq_col].std().fillna(0.0)
            n_obs    = grp[dq_col].count()
            if has_dU and du_col in sub.columns:
                mean_du = grp[du_col].mean()
                std_du  = grp[du_col].std().fillna(0.0)
            else:
                mean_du = std_du = None

            for beam in sorted(grp.groups.keys()):
                n = int(n_obs[beam])
                if has_dU and mean_du is not None:
                    row = (f"{field:<24}  {ref_ws_s:>6}  {fp_col:<16}  {freq_s:>8}  "
                           f"{pitch_s:>9}  {rot_s:>7}  {pol_s:>7}  {v:<8}  {beam:>4}  "
                           f"{mean_dq[beam]:>+9.4f}  {std_dq[beam]:>8.4f}  "
                           f"{mean_du[beam]:>+9.4f}  {std_du[beam]:>8.4f}  {n:>5}")
                else:
                    row = (f"{field:<24}  {ref_ws_s:>6}  {fp_col:<16}  {freq_s:>8}  "
                           f"{pitch_s:>9}  {rot_s:>7}  {pol_s:>7}  {v:<8}  {beam:>4}  "
                           f"{mean_dq[beam]:>+9.4f}  {std_dq[beam]:>8.4f}  {n:>5}")
                lines.append(row)
            lines.append("")  # blank line between (field, variant) blocks

    out_path = output_dir / "dq_du_correction_factors.txt"
    out_path.write_text("\n".join(lines) + "\n")
    print(f"Saved correction table: {out_path}")

    # ── companion CSV for easy Python/pandas querying ────────────────────────
    # Usage:
    #   df = pd.read_csv("dq_du_correction_factors.csv")
    #   dq = df.loc[(df.field=="REF_1324-28") & (df.variant=="bpcal") & (df.beam==0), "mean_dQ"].values[0]
    csv_cols = ["field", "ref_ws", "footprint", "centre_freq_mhz",
                "footprint_pitch_deg", "footprint_rota_deg", "pol_axis_deg",
                "variant", "beam", "mean_dQ", "std_dQ"]
    if has_dU:
        csv_cols += ["mean_dU", "std_dU"]
    csv_cols.append("n_obs")

    csv_rows = []
    for field in fields:
        df_f = df[df["ref_fieldname"] == field]
        if df_f.empty:
            continue
        for v in variants:
            sub = df_f[df_f["variant"] == v]
            if sub.empty:
                continue
            grp     = sub.groupby("beam")
            mean_dq = grp[dq_col].mean()
            std_dq  = grp[dq_col].std().fillna(0.0)
            n_obs   = grp[dq_col].count()
            if has_dU and du_col in sub.columns:
                mean_du = grp[du_col].mean()
                std_du  = grp[du_col].std().fillna(0.0)
            else:
                mean_du = std_du = None
            for beam in sorted(grp.groups.keys()):
                rec = {"field": field,
                       "ref_ws":              meta.get("ref_ws"),
                       "footprint":           meta.get('footprint_name', 'unknown'),
                       "centre_freq_mhz":     meta.get('centre_freq_mhz'),
                       "footprint_pitch_deg": meta.get('footprint_pitch_deg'),
                       "footprint_rota_deg":  meta.get('footprint_rota_deg'),
                       "pol_axis_deg":        meta.get('pol_axis_deg'),
                       "variant": v, "beam": int(beam),
                       "mean_dQ": round(mean_dq[beam], 6),
                       "std_dQ":  round(std_dq[beam],  6),
                       "n_obs":   int(n_obs[beam])}
                if has_dU and mean_du is not None:
                    rec["mean_dU"] = round(mean_du[beam], 6)
                    rec["std_dU"]  = round(std_du[beam],  6)
                csv_rows.append(rec)

    import csv as _csv
    csv_path_out    = output_dir / "dq_du_correction_factors.csv"
    readme_path_out = output_dir / "dq_du_correction_factors_README.txt"

    # ── companion README (plain text, no CSV structure) ──────────────────────
    # All provenance / schema / usage documentation lives here so that the CSV
    # itself can be pure data and open cleanly in Numbers / Excel.
    du_col_lines = (
        "  mean_dU   mean fractional Stokes-U leakage dU/I (%), signed\n"
        "  std_dU    standard deviation of dU/I (%) across observations\n"
        if has_dU else ""
    )
    du_usage_lines = (
        "  du, du_std = row.mean_dU, row.std_dU\n"
        if has_dU else ""
    )
    readme_path_out.write_text(
        "dQ/dU per-beam mean correction factors\n"
        "======================================\n"
        f"Generated by : plot_dQ_vs_beam.py  (mstool/projects/calibration-updates-2026)\n"
        f"Generated    : {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
        f"Source CSV   : {meta['csv_path']}\n"
        f"Selection    : manifest indices {meta['start_index']}\u2013{meta['end_index']},"
        f" excl {meta['exclude_indices']!r}\n"
        f"SB_REFs      : {meta['n_sbrefs']} contributing observations\n"
        f"Footprint    : {meta.get('footprint_name', 'unknown')}\n"
        f"Ref WS       : {meta.get('ref_ws', 'N/A')}  (weights.ref_ws, holography SB)\n"
        f"Centre Freq  : {meta.get('centre_freq_mhz', 'N/A')} MHz\n"
        f"Pitch        : {meta.get('footprint_pitch_deg', 'N/A')} deg\n"
        f"Rotation     : {meta.get('footprint_rota_deg', 'N/A')} deg\n"
        f"Pol Axis     : {meta.get('pol_axis_deg', 'N/A')} deg (pa_fixed)\n"
        "\n"
        "Column schema\n"
        "-------------\n"
        "  field                reference field name (e.g. REF_1324-28)\n"
        "  ref_ws               holography solution ID (weights.ref_ws); use as merge key when\n"
        "                       appending rows from different manifests\n"
        "  footprint            beam footprint name (from schedblock metadata, e.g. closepack36)\n"
        "  centre_freq_mhz      beamformer centre frequency in MHz (weights.centre_frequency)\n"
        "  footprint_pitch_deg  beam pitch in degrees (angular separation between adjacent beams)\n"
        "  footprint_rota_deg   footprint rotation angle in degrees (weights.footprint_rotation)\n"
        "  pol_axis_deg         polarisation axis angle in degrees (common.target.src1.pol_axis,\n"
        "                       pa_fixed convention)\n"
        "  variant              calibration variant: 'bpcal' (bandpass cal) or 'lcal' (leakage cal)\n"
        "                       note: obs-config columns are constant within a single-manifest run;\n"
        "                       rows from different footprints/configs can be safely appended\n"
        "  beam                 ASKAP beam index, 0-based (0-35 for closepack36)\n"
        "  mean_dQ     mean fractional Stokes-Q leakage dQ/I (%), signed, averaged\n"
        "              across all SB_REF x ODC observations for this field/variant/beam\n"
        "  std_dQ      standard deviation of dQ/I (%) across observations\n"
        + du_col_lines +
        "  n_obs       number of (SB_REF, ODC) data rows averaged for this beam\n"
        "\n"
        "Physical meaning\n"
        "----------------\n"
        "  dQ = (Q_measured / I_measured) x 100  -- on-axis Stokes-Q leakage in percent\n"
        "  dU = (U_measured / I_measured) x 100  -- on-axis Stokes-U leakage in percent\n"
        "  For an unpolarised calibrator (1934-638), any measured Q or U is pure leakage.\n"
        "  (see gain_calibration_strategy.html for the full derivation).\n"
        "\n"
        "Usage (pandas)\n"
        "--------------\n"
        "  import pandas as pd\n"
        "  df = pd.read_csv('dq_du_correction_factors.csv')\n"
        "\n"
        "  # Per-beam lookup for a specific config / field / variant / beam\n"
        "  row = df[(df.field == 'REF_1324-28')\n"
        "           & (df.variant == 'bpcal') & (df.beam == 12)].iloc[0]\n"
        "  dq, dq_std = row.mean_dQ, row.std_dQ\n"
        + du_usage_lines +
        "\n"
        "  # All 36 beams as a numpy array (for vectorised correction)\n"
        "  sub = df[(df.field == 'REF_1324-28')\n"
        "           & (df.variant == 'bpcal')].sort_values('beam')\n"
        "  dq_array = sub.mean_dQ.to_numpy()   # shape (36,), index = beam number\n"
        "\n"
        "See also\n"
        "--------\n"
        "  dq_du_correction_factors.txt   fixed-width ASCII companion, greppable\n"
        "  gain_calibration_strategy.html derivation and correction application\n"
    )
    print(f"Saved correction README: {readme_path_out}")

    # ── pure-data CSV (column header + data rows only) ────────────────────────
    # No embedded comments: opens cleanly in Numbers / Excel as a plain table.
    with csv_path_out.open("w", newline="") as fh:
        writer = _csv.DictWriter(fh, fieldnames=csv_cols)
        writer.writeheader()
        writer.writerows(csv_rows)
    print(f"Saved correction CSV:   {csv_path_out}")


# ── Portable query helper ─────────────────────────────────────────────────────

def lookup_correction(csv_path, field, variant, beam):
    """Return dQ/dU correction factors for a given reference field, variant and beam.

    This function is importable so other scripts can query the correction table
    without re-running the full plot pipeline.

    Parameters
    ----------
    csv_path : str or pathlib.Path
        Path to ``dq_du_correction_factors.csv`` produced by this script.
    field : str
        Reference field name, e.g. ``"REF_1324-28"``.
    variant : str
        Calibration variant: ``"bpcal"`` or ``"lcal"``.
    beam : int
        Beam index (0–35).

    Returns
    -------
    dict
        Keys: ``mean_dQ``, ``std_dQ``, ``n_obs``, and (when present in the
        CSV) ``mean_dU``, ``std_dU``.  All numeric values are native Python
        floats/ints so the dict is directly JSON-serialisable.

    Raises
    ------
    FileNotFoundError
        If *csv_path* does not exist.
    KeyError
        If no row matches the requested ``(field, variant, beam)``
        combination.  The error message lists available values.

    Examples
    --------
    Minimal usage::

        from plot_dQ_vs_beam import lookup_correction
        r = lookup_correction("dq_du_correction_factors.csv",
                              "REF_1324-28", "bpcal", 12)
        print(f"dQ = {r['mean_dQ']:+.4f} ± {r['std_dQ']:.4f} %")
        if "mean_dU" in r:
            print(f"dU = {r['mean_dU']:+.4f} ± {r['std_dU']:.4f} %")

    Bulk lookup with pandas::

        import pandas as pd
        df = pd.read_csv("dq_du_correction_factors.csv")
        sub = df[(df.field == "REF_1324-28") & (df.variant == "bpcal")]
        # sub now has one row per beam for that field/variant
    """
    import pandas as _pd

    csv_path = Path(csv_path)
    if not csv_path.exists():
        raise FileNotFoundError(f"Correction CSV not found: {csv_path}")

    df = _pd.read_csv(csv_path)

    mask = (
        (df["field"]   == str(field))
        & (df["variant"] == str(variant))
        & (df["beam"]    == int(beam))
    )
    row = df.loc[mask]

    if row.empty:
        available_fields   = sorted(df["field"].unique().tolist())
        available_variants = sorted(df["variant"].unique().tolist())
        available_beams    = sorted(int(b) for b in df["beam"].unique())
        raise KeyError(
            f"No entry for (field={field!r}, variant={variant!r}, beam={beam}).\n"
            f"  Available fields  : {available_fields}\n"
            f"  Available variants: {available_variants}\n"
            f"  Available beams   : {available_beams}"
        )

    r = row.iloc[0]
    result = {
        "mean_dQ": float(r["mean_dQ"]),
        "std_dQ":  float(r["std_dQ"]),
        "n_obs":   int(r["n_obs"]),
    }
    if "mean_dU" in r.index and not _pd.isna(r["mean_dU"]):
        result["mean_dU"] = float(r["mean_dU"])
        result["std_dU"]  = float(r["std_dU"])
    return result


def main():
    parser = argparse.ArgumentParser(
        description="Plot signed dQ (and optionally dU) vs beam per reference field",
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
        "--variant", choices=["bpcal", "lcal", "both"], default="both",
        help="Calibration variant(s) to plot.",
    )
    parser.add_argument(
        "--dU", action="store_true",
        help="Also produce a matching figure for signed dU.",
    )
    parser.add_argument(
        "--fields", default=None,
        help="Comma-separated ref_fieldname values to include (e.g. 'REF_1324-28,REF_0324-28'). "
             "Case-insensitive partial match: '1324-28' matches 'REF_1324-28'. "
             "Omit to plot all fields selected by the manifest.",
    )
    parser.add_argument(
        "--ylim", type=float, default=2.5, metavar="PCT",
        help="Minimum symmetric y-axis half-range in %% (default ±2.5%%). "
             "Automatically expands if data exceeds this bound. Pass 0 to fully auto-scale.",
    )
    parser.add_argument("--show", action="store_true",
                        help="Display plots interactively after saving.")
    parser.add_argument("--force", action="store_true",
                        help="Regenerate PNGs even if they already exist on disk.")

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

    # ── ref_ws consistency check ──────────────────────────────────────────────
    # All selected SB_REFs must share the same holography solution (ref_ws) so
    # that the beam geometry and correction factors are physically comparable.
    if "ref_ws" in df.columns:
        unique_ref_ws = df["ref_ws"].dropna().unique()
        if len(unique_ref_ws) > 1:
            from collections import Counter
            counts = Counter(df["ref_ws"].dropna().astype(int))
            majority, _ = counts.most_common(1)[0]
            outlier_sbs = (
                df[df["ref_ws"] != majority][["sb_ref", "ref_ws"]]
                .drop_duplicates()
                .sort_values("sb_ref")
            )
            print()
            print("ERROR: ref_ws consistency check FAILED in master CSV.")
            print(f"  Expected ref_ws = {majority}")
            print("  Outlier SB_REFs:")
            for _, r in outlier_sbs.iterrows():
                print(f"    SB_REF {r['sb_ref']}: ref_ws = {int(r['ref_ws'])}")
            print("  All SB_REFs must share the same holography solution.")
            print("  Please re-run build_phase1_master_table.py or adjust the manifest.")
            print()
            sys.exit(1)
        elif len(unique_ref_ws) == 1:
            print(f"ref_ws consistency check PASSED: ref_ws = {int(unique_ref_ws[0])}")

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

    variants  = ["bpcal", "lcal"] if args.variant == "both" else [args.variant]
    quantities = [("leak_q_over_i_signed_pct", "dQ")]
    if args.dU:
        quantities.append(("leak_u_over_i_signed_pct", "dU"))

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
                # Reconstruct the output path the same way make_figure() does
                qty_tag   = "d" + col.replace("leak_", "").replace("_over_i_signed_pct", "").upper()
                field_tag = field.replace("/", "-")
                out_path  = output_dir / f"{qty_tag}_vs_beam_{field_tag}_{v}.png"
                if out_path.exists() and not args.force:
                    print(f"  Skip (exists): {out_path.name}")
                    continue
                # Mean across all (odc, sb_ref) for this beam position
                mean_per_beam = sub.groupby("beam")[col].mean()
                make_figure(sub, field, v, col, label, output_dir, args.show,
                            ylim=args.ylim if args.ylim > 0 else None,
                            mean_per_beam=mean_per_beam)

    # ── ASCII correction-factor lookup table ────────────────────────────────
    # Derive observation-config columns from the master CSV.
    # In a single-manifest run these are constant across all rows; take the
    # modal (most common) non-null value so mixed runs degrade gracefully.
    def _modal_str(col):
        if col not in df.columns:
            return None
        vals = df[col].dropna()
        vals = vals[vals.astype(str).str.strip() != ""]
        return str(vals.mode().iloc[0]) if not vals.empty else None

    def _modal_num(col):
        if col not in df.columns:
            return None
        vals = pd.to_numeric(df[col], errors="coerce").dropna()
        if vals.empty:
            return None
        return float(vals.round(4).mode().iloc[0])

    footprint_name       = _modal_str("footprint_name") or "unknown"
    centre_freq_val      = _modal_num("centre_freq_mhz")
    pitch_val            = _modal_num("pitch_deg_from_schedblock")
    rotation_val         = _modal_num("footprint_rota_deg")
    pol_axis_val         = _modal_num("pol_axis_deg")
    ref_ws_val           = _modal_num("ref_ws")

    write_correction_table(
        df, fields_to_plot, variants,
        has_dU=args.dU,
        output_dir=output_dir,
        meta={
            "csv_path":               str(csv_path),
            "start_index":            args.start_index,
            "end_index":              args.end_index,
            "exclude_indices":        args.exclude_indices,
            "n_sbrefs":               df["sb_ref"].nunique(),
            "footprint_name":      footprint_name,
            "ref_ws":              int(ref_ws_val) if ref_ws_val is not None else None,
            "centre_freq_mhz":     centre_freq_val,
            "footprint_pitch_deg": pitch_val,
            "footprint_rota_deg":  rotation_val,
            "pol_axis_deg":        pol_axis_val,
        },
    )


if __name__ == "__main__":
    main()
