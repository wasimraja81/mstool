#!/usr/bin/env python3

import argparse
import csv
import math
from collections import defaultdict
from pathlib import Path
from statistics import median


def to_float(value):
    try:
        if value is None or value == "":
            return None
        return float(value)
    except Exception:
        return None


def percentile(values, q):
    if not values:
        return None
    data = sorted(values)
    if len(data) == 1:
        return data[0]
    pos = (len(data) - 1) * q
    low = math.floor(pos)
    high = math.ceil(pos)
    if low == high:
        return data[low]
    frac = pos - low
    return data[low] * (1.0 - frac) + data[high] * frac


def robust_z(value, population):
    clean = [v for v in population if v is not None]
    if value is None or not clean:
        return None
    med = median(clean)
    abs_dev = [abs(v - med) for v in clean]
    mad = median(abs_dev) if abs_dev else None
    if mad is None or mad == 0:
        return 0.0
    return (value - med) / (1.4826 * mad)


def mad(values):
    clean = [v for v in values if v is not None]
    if not clean:
        return None
    med = median(clean)
    return median([abs(v - med) for v in clean])


def find_stats_plot_png(assessment_dir, variant, sb_ref=None):
    if not assessment_dir:
        return ""
    path = Path(assessment_dir)
    if not path.exists() or not path.is_dir():
        return ""
    matches = sorted(path.glob("*leakage_stats*.png"))
    if not matches:
        return ""

    if sb_ref:
        sb_token = f"SB_REF-{sb_ref}_"
        specific = [p for p in matches if sb_token in p.name]
        if specific:
            matches = specific

    variant_lower = str(variant).strip().lower()
    if variant_lower == "lcal":
        variant_matches = [p for p in matches if ".lcal." in p.name or p.name.endswith("leakage_stats.lcal.png")]
    else:
        variant_matches = [p for p in matches if ".lcal." not in p.name]

    if variant_matches:
        return str(variant_matches[0])
    return ""


def read_master_rows(csv_path: Path):
    rows = []
    with csv_path.open() as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row.get("leakage_parse_ok") not in {"True", "true", True}:
                continue
            leak_l = to_float(row.get("leak_l_over_i_pct"))
            if leak_l is None:
                continue
            row["leak_l_over_i_pct"] = leak_l
            row["leak_q_over_i_pct"] = to_float(row.get("leak_q_over_i_pct"))
            row["leak_u_over_i_pct"] = to_float(row.get("leak_u_over_i_pct"))
            rows.append(row)
    return rows


def aggregate_beam_x_field_at_fixed_odc(rows):
    grouped = defaultdict(list)
    grouped_q = defaultdict(list)
    grouped_u = defaultdict(list)
    sb_refs = defaultdict(set)

    for row in rows:
        key = (
            row["odc_weight"],
            row["variant"],
            int(row["beam"]),
            row["ref_fieldname"],
        )
        grouped[key].append(row["leak_l_over_i_pct"])
        if row["leak_q_over_i_pct"] is not None:
            grouped_q[key].append(row["leak_q_over_i_pct"])
        if row["leak_u_over_i_pct"] is not None:
            grouped_u[key].append(row["leak_u_over_i_pct"])
        sb_refs[key].add(row["sb_ref"])

    out = []
    for key, vals in grouped.items():
        odc_weight, variant, beam, ref_fieldname = key
        qvals = grouped_q.get(key, [])
        uvals = grouped_u.get(key, [])
        out.append(
            {
                "odc_weight": odc_weight,
                "variant": variant,
                "beam": beam,
                "ref_fieldname": ref_fieldname,
                "median_l_over_i": median(vals),
                "p90_l_over_i": percentile(vals, 0.90),
                "median_q_over_i": median(qvals) if qvals else None,
                "p90_q_over_i": percentile(qvals, 0.90) if qvals else None,
                "median_u_over_i": median(uvals) if uvals else None,
                "p90_u_over_i": percentile(uvals, 0.90) if uvals else None,
                "count_sb_ref": len(sb_refs[key]),
                "count_samples": len(vals),
            }
        )

    out.sort(key=lambda r: (r["odc_weight"], r["variant"], r["beam"], r["ref_fieldname"]))
    return out


def aggregate_beam_x_odc_at_fixed_field(rows):
    grouped = defaultdict(list)
    grouped_q = defaultdict(list)
    grouped_u = defaultdict(list)
    sb_refs = defaultdict(set)

    for row in rows:
        key = (
            row["ref_fieldname"],
            row["variant"],
            int(row["beam"]),
            row["odc_weight"],
        )
        grouped[key].append(row["leak_l_over_i_pct"])
        if row["leak_q_over_i_pct"] is not None:
            grouped_q[key].append(row["leak_q_over_i_pct"])
        if row["leak_u_over_i_pct"] is not None:
            grouped_u[key].append(row["leak_u_over_i_pct"])
        sb_refs[key].add(row["sb_ref"])

    out = []
    for key, vals in grouped.items():
        ref_fieldname, variant, beam, odc_weight = key
        qvals = grouped_q.get(key, [])
        uvals = grouped_u.get(key, [])
        out.append(
            {
                "ref_fieldname": ref_fieldname,
                "variant": variant,
                "beam": beam,
                "odc_weight": odc_weight,
                "median_l_over_i": median(vals),
                "p90_l_over_i": percentile(vals, 0.90),
                "median_q_over_i": median(qvals) if qvals else None,
                "p90_q_over_i": percentile(qvals, 0.90) if qvals else None,
                "median_u_over_i": median(uvals) if uvals else None,
                "p90_u_over_i": percentile(uvals, 0.90) if uvals else None,
                "count_sb_ref": len(sb_refs[key]),
                "count_samples": len(vals),
            }
        )

    out.sort(key=lambda r: (r["ref_fieldname"], r["variant"], r["beam"], r["odc_weight"]))
    return out


def build_field_effect_scores(beam_x_field_rows, sb_refs_by_candidate=None, plot_links_by_candidate=None):
    sb_refs_by_candidate = sb_refs_by_candidate or {}
    plot_links_by_candidate = plot_links_by_candidate or {}
    beam_baseline = {}
    by_baseline_key = defaultdict(list)
    for row in beam_x_field_rows:
        by_baseline_key[(row["odc_weight"], row["variant"], row["beam"])].append(row["median_l_over_i"])
    for key, vals in by_baseline_key.items():
        beam_baseline[key] = median(vals)

    per_field_beam_deltas = defaultdict(list)
    per_field_all_vals = defaultdict(list)
    per_field_all_vals_q = defaultdict(list)
    per_field_all_vals_u = defaultdict(list)
    for row in beam_x_field_rows:
        key = (row["odc_weight"], row["variant"], row["ref_fieldname"])
        baseline = beam_baseline[(row["odc_weight"], row["variant"], row["beam"])]
        delta = row["median_l_over_i"] - baseline
        per_field_beam_deltas[key].append(delta)
        per_field_all_vals[key].append(row["median_l_over_i"])
        if row.get("median_q_over_i") is not None:
            per_field_all_vals_q[key].append(row["median_q_over_i"])
        if row.get("median_u_over_i") is not None:
            per_field_all_vals_u[key].append(row["median_u_over_i"])

    groups = defaultdict(list)
    for (odc_weight, variant, _field), vals in per_field_beam_deltas.items():
        groups[(odc_weight, variant)].append(median(vals))

    out = []
    for key, deltas in per_field_beam_deltas.items():
        odc_weight, variant, ref_fieldname = key
        delta_score = median(deltas)
        vals = per_field_all_vals[key]
        qvals = per_field_all_vals_q.get(key, [])
        uvals = per_field_all_vals_u.get(key, [])
        med_beam = median(vals) if vals else None
        affected = sum(1 for d in deltas if d > 0)
        z = robust_z(delta_score, groups[(odc_weight, variant)])
        sb_refs = sorted(sb_refs_by_candidate.get(key, set()))
        plot_map = plot_links_by_candidate.get(key, {})
        plot_links = []
        for sb in sb_refs:
            plot_links.append(f"{sb}|{plot_map.get(sb, '')}")
        out.append(
            {
                "odc_weight": odc_weight,
                "variant": variant,
                "ref_fieldname": ref_fieldname,
                "n_candidates": len(sb_refs),
                "sb_ref_values": ";".join(sb_refs),
                "sb_ref_plot_links": ";".join(plot_links),
                "beam_median_l_over_i": med_beam,
                "beam_mean_l_over_i": (sum(vals) / len(vals)) if vals else None,
                "beam_mad_l_over_i": mad(vals),
                "beam_min_l_over_i": min(vals) if vals else None,
                "beam_max_l_over_i": max(vals) if vals else None,
                "beam_median_q_over_i": median(qvals) if qvals else None,
                "beam_mean_q_over_i": (sum(qvals) / len(qvals)) if qvals else None,
                "beam_mad_q_over_i": mad(qvals),
                "beam_min_q_over_i": min(qvals) if qvals else None,
                "beam_max_q_over_i": max(qvals) if qvals else None,
                "beam_median_u_over_i": median(uvals) if uvals else None,
                "beam_mean_u_over_i": (sum(uvals) / len(uvals)) if uvals else None,
                "beam_mad_u_over_i": mad(uvals),
                "beam_min_u_over_i": min(uvals) if uvals else None,
                "beam_max_u_over_i": max(uvals) if uvals else None,
                "delta_to_beam_baseline_f": delta_score,
                "affected_beam_count_f": affected,
                "p95_l_over_i": percentile(vals, 0.95),
                "p95_q_over_i": percentile(qvals, 0.95) if qvals else None,
                "p95_u_over_i": percentile(uvals, 0.95) if uvals else None,
                "robust_z": z,
            }
        )

    out.sort(key=lambda r: (r["odc_weight"], r["variant"], r["ref_fieldname"]))
    return out


def build_odc_effect_scores(beam_x_odc_rows, sb_refs_by_candidate=None, plot_links_by_candidate=None):
    sb_refs_by_candidate = sb_refs_by_candidate or {}
    plot_links_by_candidate = plot_links_by_candidate or {}
    beam_baseline = {}
    by_baseline_key = defaultdict(list)
    for row in beam_x_odc_rows:
        by_baseline_key[(row["ref_fieldname"], row["variant"], row["beam"])].append(row["median_l_over_i"])
    for key, vals in by_baseline_key.items():
        beam_baseline[key] = median(vals)

    per_odc_beam_deltas = defaultdict(list)
    per_odc_all_vals = defaultdict(list)
    per_odc_all_vals_q = defaultdict(list)
    per_odc_all_vals_u = defaultdict(list)
    for row in beam_x_odc_rows:
        key = (row["ref_fieldname"], row["variant"], row["odc_weight"])
        baseline = beam_baseline[(row["ref_fieldname"], row["variant"], row["beam"])]
        delta = row["median_l_over_i"] - baseline
        per_odc_beam_deltas[key].append(delta)
        per_odc_all_vals[key].append(row["median_l_over_i"])
        if row.get("median_q_over_i") is not None:
            per_odc_all_vals_q[key].append(row["median_q_over_i"])
        if row.get("median_u_over_i") is not None:
            per_odc_all_vals_u[key].append(row["median_u_over_i"])

    groups = defaultdict(list)
    for (ref_fieldname, variant, _odc), vals in per_odc_beam_deltas.items():
        groups[(ref_fieldname, variant)].append(median(vals))

    out = []
    for key, deltas in per_odc_beam_deltas.items():
        ref_fieldname, variant, odc_weight = key
        delta_score = median(deltas)
        vals = per_odc_all_vals[key]
        qvals = per_odc_all_vals_q.get(key, [])
        uvals = per_odc_all_vals_u.get(key, [])
        med_beam = median(vals) if vals else None
        affected = sum(1 for d in deltas if d > 0)
        z = robust_z(delta_score, groups[(ref_fieldname, variant)])
        sb_refs = sorted(sb_refs_by_candidate.get(key, set()))
        plot_map = plot_links_by_candidate.get(key, {})
        plot_links = []
        for sb in sb_refs:
            plot_links.append(f"{sb}|{plot_map.get(sb, '')}")
        out.append(
            {
                "ref_fieldname": ref_fieldname,
                "variant": variant,
                "odc_weight": odc_weight,
                "n_candidates": len(sb_refs),
                "sb_ref_values": ";".join(sb_refs),
                "sb_ref_plot_links": ";".join(plot_links),
                "beam_median_l_over_i": med_beam,
                "beam_mean_l_over_i": (sum(vals) / len(vals)) if vals else None,
                "beam_mad_l_over_i": mad(vals),
                "beam_min_l_over_i": min(vals) if vals else None,
                "beam_max_l_over_i": max(vals) if vals else None,
                "beam_median_q_over_i": median(qvals) if qvals else None,
                "beam_mean_q_over_i": (sum(qvals) / len(qvals)) if qvals else None,
                "beam_mad_q_over_i": mad(qvals),
                "beam_min_q_over_i": min(qvals) if qvals else None,
                "beam_max_q_over_i": max(qvals) if qvals else None,
                "beam_median_u_over_i": median(uvals) if uvals else None,
                "beam_mean_u_over_i": (sum(uvals) / len(uvals)) if uvals else None,
                "beam_mad_u_over_i": mad(uvals),
                "beam_min_u_over_i": min(uvals) if uvals else None,
                "beam_max_u_over_i": max(uvals) if uvals else None,
                "delta_to_beam_baseline_o": delta_score,
                "affected_beam_count_o": affected,
                "p95_l_over_i": percentile(vals, 0.95),
                "p95_q_over_i": percentile(qvals, 0.95) if qvals else None,
                "p95_u_over_i": percentile(uvals, 0.95) if uvals else None,
                "robust_z": z,
            }
        )

    out.sort(key=lambda r: (r["ref_fieldname"], r["variant"], r["odc_weight"]))
    return out


def write_csv(path: Path, rows, fieldnames):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser(description="Build Phase-2 isolation tables from leakage_master_table.csv")
    parser.add_argument(
        "--input-csv",
        default=str(Path.home() / "DATA" / "reffield-average" / "leakage_master_table.csv"),
        help="Input master CSV",
    )
    parser.add_argument(
        "--output-dir",
        default=str(Path.home() / "DATA" / "reffield-average" / "phase2"),
        help="Directory for Phase-2 output tables",
    )
    parser.add_argument(
        "--summary-md",
        default=str(Path.home() / "DATA" / "reffield-average" / "phase2" / "phase2_mvp_summary.md"),
        help="Markdown summary output",
    )
    args = parser.parse_args()

    input_csv = Path(args.input_csv)
    output_dir = Path(args.output_dir)
    summary_md = Path(args.summary_md)

    rows = read_master_rows(input_csv)

    sb_refs_by_field_candidate = defaultdict(set)
    sb_refs_by_odc_candidate = defaultdict(set)
    plot_links_by_field_candidate = defaultdict(dict)
    plot_links_by_odc_candidate = defaultdict(dict)
    plot_cache = {}
    for row in rows:
        field_key = (row["odc_weight"], row["variant"], row["ref_fieldname"])
        odc_key = (row["ref_fieldname"], row["variant"], row["odc_weight"])
        sb_ref_value = str(row["sb_ref"])
        sb_refs_by_field_candidate[field_key].add(sb_ref_value)
        sb_refs_by_odc_candidate[odc_key].add(sb_ref_value)

        cache_key = (row.get("assessment_dir", ""), row["variant"], sb_ref_value)
        if cache_key not in plot_cache:
            plot_cache[cache_key] = find_stats_plot_png(row.get("assessment_dir", ""), row["variant"], sb_ref_value)
        plot_path = plot_cache[cache_key]
        if plot_path:
            plot_links_by_field_candidate[field_key][sb_ref_value] = plot_path
            plot_links_by_odc_candidate[odc_key][sb_ref_value] = plot_path

    beam_x_field = aggregate_beam_x_field_at_fixed_odc(rows)
    beam_x_odc = aggregate_beam_x_odc_at_fixed_field(rows)
    field_scores = build_field_effect_scores(beam_x_field, sb_refs_by_field_candidate, plot_links_by_field_candidate)
    odc_scores = build_odc_effect_scores(beam_x_odc, sb_refs_by_odc_candidate, plot_links_by_odc_candidate)

    p1 = output_dir / "beam_x_field_at_fixed_odc.csv"
    p2 = output_dir / "field_effect_scores_at_fixed_odc.csv"
    p3 = output_dir / "beam_x_odc_at_fixed_field.csv"
    p4 = output_dir / "odc_effect_scores_at_fixed_field.csv"

    write_csv(
        p1,
        beam_x_field,
        [
            "odc_weight", "variant", "beam", "ref_fieldname",
            "median_l_over_i", "p90_l_over_i",
            "median_q_over_i", "median_u_over_i",
            "count_sb_ref", "count_samples",
        ],
    )
    write_csv(
        p2,
        field_scores,
        [
            "odc_weight",
            "variant",
            "ref_fieldname",
            "n_candidates",
            "sb_ref_values",
            "sb_ref_plot_links",
            "beam_median_l_over_i",
            "beam_mean_l_over_i",
            "beam_mad_l_over_i",
            "beam_min_l_over_i",
            "beam_max_l_over_i",
            "beam_median_q_over_i",
            "beam_median_u_over_i",
            "delta_to_beam_baseline_f",
            "affected_beam_count_f",
            "p95_l_over_i",
            "robust_z",
        ],
    )
    write_csv(
        p3,
        beam_x_odc,
        [
            "ref_fieldname", "variant", "beam", "odc_weight",
            "median_l_over_i", "p90_l_over_i",
            "median_q_over_i", "median_u_over_i",
            "count_sb_ref", "count_samples",
        ],
    )
    write_csv(
        p4,
        odc_scores,
        [
            "ref_fieldname",
            "variant",
            "odc_weight",
            "n_candidates",
            "sb_ref_values",
            "sb_ref_plot_links",
            "beam_median_l_over_i",
            "beam_mean_l_over_i",
            "beam_mad_l_over_i",
            "beam_min_l_over_i",
            "beam_max_l_over_i",
            "beam_median_q_over_i",
            "beam_median_u_over_i",
            "delta_to_beam_baseline_o",
            "affected_beam_count_o",
            "p95_l_over_i",
            "robust_z",
        ],
    )

    summary_md.parent.mkdir(parents=True, exist_ok=True)
    summary_md.write_text(
        "# Phase-2 MVP Summary\n\n"
        f"- Input master CSV: {input_csv}\n"
        f"- Input parse rows: {len(rows)}\n"
        f"- Output: {p1}\n"
        f"- Output: {p2}\n"
        f"- Output: {p3}\n"
        f"- Output: {p4}\n"
        f"- Rows in beam_x_field_at_fixed_odc: {len(beam_x_field)}\n"
        f"- Rows in field_effect_scores_at_fixed_odc: {len(field_scores)}\n"
        f"- Rows in beam_x_odc_at_fixed_field: {len(beam_x_odc)}\n"
        f"- Rows in odc_effect_scores_at_fixed_field: {len(odc_scores)}\n"
    )

    print(f"Wrote {p1}")
    print(f"Wrote {p2}")
    print(f"Wrote {p3}")
    print(f"Wrote {p4}")
    print(f"Wrote {summary_md}")
    print(
        "SUMMARY "
        f"input_rows={len(rows)} "
        f"beam_x_field={len(beam_x_field)} "
        f"field_scores={len(field_scores)} "
        f"beam_x_odc={len(beam_x_odc)} "
        f"odc_scores={len(odc_scores)}"
    )


if __name__ == "__main__":
    main()
