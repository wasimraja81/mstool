#!/usr/bin/env python3

import argparse
import csv
import math
import re
from pathlib import Path


def normalize_preflag_value(token: str) -> str:
    token_lc = token.strip().lower()
    if token_lc in {"true", "on", "yes", "1", "insitupreflags"}:
        return "true"
    if token_lc in {"false", "off", "no", "0", "none"}:
        return "false"
    return ""


def build_strategy_suffix(amp_strategy: str, do_preflag: str) -> str:
    suffix = ""
    if amp_strategy:
        suffix += f"_AMP_STRATEGY-{amp_strategy}"
    if do_preflag == "true":
        suffix += "-insituPreflags"
    return suffix


def parse_exclude_indices(raw: str):
    ranges = []
    if not raw:
        return ranges
    for token in raw.replace(" ", "").split(","):
        if not token:
            continue
        if "-" in token:
            start_s, end_s = token.split("-", 1)
            start = int(start_s)
            end = int(end_s)
            if start > end:
                raise ValueError(f"Invalid exclude range '{token}'")
            ranges.append((start, end))
        else:
            idx = int(token)
            ranges.append((idx, idx))
    return ranges


def is_excluded(idx: int, ranges) -> bool:
    for start, end in ranges:
        if start <= idx <= end:
            return True
    return False


def parse_manifest_rows(manifest_path: Path, start_index: int, end_index: int, exclude_ranges):
    rows = []
    auto_row_index = 0
    default_amp = "multiply"
    default_preflag = "true"
    line_no = 0

    for raw_line in manifest_path.read_text().splitlines():
        line_no += 1
        line = raw_line.split("#", 1)[0].strip()
        if not line:
            continue

        cfg_match = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)=(.+)$", line)
        if cfg_match:
            cfg_key = cfg_match.group(1)
            cfg_val = cfg_match.group(2).strip()
            if cfg_key == "AMP_STRATEGY":
                default_amp = cfg_val
            elif cfg_key in {
                "DO_PREFLAG_REFTABLE",
                "PREFLAGGING_STRATEGY",
                "PREFLAG_STRATEGY",
                "FLAG_STRATEGY",
            }:
                normalized = normalize_preflag_value(cfg_val)
                if normalized:
                    default_preflag = normalized
            continue

        cols = re.split(r"[\s,]+", line)
        if not cols:
            continue

        if re.fullmatch(r"\d+", cols[0]):
            row_index = int(cols[0])
            cols = cols[1:]
        else:
            row_index = auto_row_index
        auto_row_index += 1

        if len(cols) < 4:
            continue

        if cols[0].lower() in {"sb_ref", "sbref"}:
            continue

        if row_index < start_index or row_index > end_index or is_excluded(row_index, exclude_ranges):
            continue

        sb_ref, sb_1934, sb_holo, sb_target_1934 = cols[0:4]
        amp_strategy = default_amp
        do_preflag = default_preflag
        odc_weight = ""
        ref_fieldname = ""

        for token in cols[4:8]:
            if "=" not in token:
                continue
            key, value = token.split("=", 1)
            key = key.upper().replace("-", "_")
            value = value.strip()
            if key in {"ODC_WEIGHT", "ODC_WEIGHT_ID", "ODC", "WEIGHT_ID"}:
                odc_weight = value
            elif key == "AMP_STRATEGY":
                amp_strategy = value
            elif key in {
                "DO_PREFLAG_REFTABLE",
                "DO_PREFLAG",
                "PREFLAGGING_STRATEGY",
                "PREFLAG_STRATEGY",
                "FLAG_STRATEGY",
            }:
                normalized = normalize_preflag_value(value)
                if normalized:
                    do_preflag = normalized
            elif key == "REF_FIELDNAME":
                ref_fieldname = value

        tuple_rel = (
            f"SB_REF-{sb_ref}_SB_1934-{sb_1934}_SB_HOLO-{sb_holo}"
            f"{build_strategy_suffix(amp_strategy, do_preflag)}"
        )

        rows.append(
            {
                "manifest_index": row_index,
                "sb_ref": sb_ref,
                "sb_1934": sb_1934,
                "sb_holo": sb_holo,
                "sb_target_1934": sb_target_1934,
                "odc_weight": odc_weight,
                "ref_fieldname": ref_fieldname,
                "amp_strategy": amp_strategy,
                "do_preflag_reftable": do_preflag,
                "tuple_rel_path": tuple_rel,
            }
        )

    rows.sort(key=lambda row: row["manifest_index"])
    return rows


def parse_footprint_name(metadata_dir: Path, sb_ref: str) -> str:
    """Read the footprint name from the schedblock-info file for *sb_ref*.

    Tries ``weights.footprint_name`` first (set by the ODC weight configuration),
    then falls back to ``common.target.src%d.footprint.name``.
    Returns an empty string if neither is found.
    """
    preferred = metadata_dir / f"schedblock-info-{sb_ref}.txt"
    candidates = [preferred] if preferred.exists() else []
    candidates.extend(sorted(metadata_dir.glob("schedblock-info-*.txt")))

    for path in candidates:
        try:
            content = path.read_text()
        except Exception:
            continue
        for pattern in [
            r"weights\.footprint_name\s*=\s*(\S+)",
            r"common\.target\.src%d\.footprint\.name\s*=\s*(\S+)",
        ]:
            match = re.search(pattern, content)
            if match:
                return match.group(1).strip()

    return ""


def parse_obs_metadata(metadata_dir: Path, sb_ref: str) -> dict:
    """Parse observation-level beam configuration from the schedblock-info file.

    Extracts:
      - weights_id            (weights.id)
      - centre_freq_mhz       (weights.centre_frequency)
      - footprint_rotation_deg (weights.footprint_rotation)
      - pol_axis_deg           (common.target.src%d.pol_axis, angle component)

    Returns a dict with those keys; missing values are None.
    """
    preferred = metadata_dir / f"schedblock-info-{sb_ref}.txt"
    candidates = [preferred] if preferred.exists() else []
    candidates.extend(sorted(metadata_dir.glob("schedblock-info-*.txt")))

    result: dict = {
        "weights_id":            None,
        "centre_freq_mhz":       None,
        "footprint_rotation_deg": None,
        "pol_axis_deg":           None,
    }
    _int_patterns = {
        "weights_id": r"weights\.id\s*=\s*(\d+)",
    }
    _float_patterns = {
        "centre_freq_mhz":        r"weights\.centre_frequency\s*=\s*([-+]?\d*\.?\d+)",
        "footprint_rotation_deg": r"weights\.footprint_rotation\s*=\s*([-+]?\d*\.?\d+)",
    }
    # pol_axis: e.g. "[pa_fixed, 0.0]" — extract the angle (second element)
    _pol_pattern = r"common\.target\.src%d\.pol_axis\s*=\s*\[.*?,\s*([-+]?\d*\.?\d+)"

    for path in candidates:
        try:
            content = path.read_text()
        except Exception:
            continue
        for key, pattern in _int_patterns.items():
            if result[key] is None:
                m = re.search(pattern, content)
                if m:
                    result[key] = int(m.group(1))
        for key, pattern in _float_patterns.items():
            if result[key] is None:
                m = re.search(pattern, content)
                if m:
                    result[key] = float(m.group(1))
        if result["pol_axis_deg"] is None:
            m = re.search(_pol_pattern, content)
            if m:
                result["pol_axis_deg"] = float(m.group(1))
        if all(v is not None for v in result.values()):
            break

    return result


def parse_pitch_deg(metadata_dir: Path, sb_ref: str):
    preferred = metadata_dir / f"schedblock-info-{sb_ref}.txt"
    candidates = [preferred] if preferred.exists() else []
    candidates.extend(sorted(metadata_dir.glob("schedblock-info-*.txt")))

    for path in candidates:
        try:
            content = path.read_text()
        except Exception:
            continue

        for pattern in [
            r"common\.target\.src%d\.footprint\.pitch\s*=\s*([-+]?\d*\.?\d+)",
            r"weights\.footprint_pitch\s*=\s*([-+]?\d*\.?\d+)",
        ]:
            match = re.search(pattern, content)
            if match:
                return float(match.group(1)), str(path)

    return None, ""


def parse_ra_to_deg(ra_hms: str):
    parts = ra_hms.strip().split(":")
    if len(parts) != 3:
        return None
    h, m, s = [float(value) for value in parts]
    return 15.0 * (h + (m / 60.0) + (s / 3600.0))


def parse_dec_to_deg(dec_dms: str):
    token = dec_dms.strip()
    sign = -1.0 if token.startswith("-") else 1.0
    token = token.lstrip("+-")
    if ":" in token:
        parts = token.split(":")
    else:
        parts = token.replace(".", ":", 2).split(":")
    if len(parts) != 3:
        return None
    d, m, s = [float(value) for value in parts]
    return sign * (d + (m / 60.0) + (s / 3600.0))


def parse_footprint(footprint_path: Path):
    beam_map = {}
    for raw_line in footprint_path.read_text().splitlines():
        line = raw_line.strip()
        if not line:
            continue

        match = re.match(
            r"^(\d+)\s+\(\s*([-+]?\d*\.?\d+)\s+([-+]?\d*\.?\d+)\)\s+([^,]+),([^\s]+)$",
            line,
        )
        if not match:
            continue

        beam = int(match.group(1))
        off_x = float(match.group(2))
        off_y = float(match.group(3))
        ra_hms = match.group(4).strip()
        dec_dms = match.group(5).strip()

        beam_map[beam] = {
            "offset_x_deg": off_x,
            "offset_y_deg": off_y,
            "beam_centre_ra_hms": ra_hms,
            "beam_centre_dec_dms": dec_dms,
            "beam_centre_ra_deg": parse_ra_to_deg(ra_hms),
            "beam_centre_dec_deg": parse_dec_to_deg(dec_dms),
        }

    return beam_map


def compute_offset_nn_spacing(beam_map):
    points = [(value["offset_x_deg"], value["offset_y_deg"]) for _, value in sorted(beam_map.items())]
    if len(points) < 2:
        return None

    nearest_distances = []
    for i, (x1, y1) in enumerate(points):
        best = None
        for j, (x2, y2) in enumerate(points):
            if i == j:
                continue
            d = math.hypot(x1 - x2, y1 - y2)
            if best is None or d < best:
                best = d
        if best is not None:
            nearest_distances.append(best)

    if not nearest_distances:
        return None

    return sum(nearest_distances) / len(nearest_distances)


def parse_leakage_metrics(txt_path: Path):
    metrics = {
        "q_over_i_pct": None,
        "u_over_i_pct": None,
        "l_over_i_pct": None,
        "v_over_i_pct": None,
        "q_over_i_signed_pct": None,
        "u_over_i_signed_pct": None,
        "l_over_i_signed_pct": None,
        "v_over_i_signed_pct": None,
        "q_over_i_mad_pct": None,
        "u_over_i_mad_pct": None,
        "l_over_i_mad_pct": None,
        "v_over_i_mad_pct": None,
        "channel_count_detected": 0,
    }

    patterns = [
        ("q_over_i_pct", re.compile(r"\|Q\|/I\s*=\s*([-+]?\d*\.?\d+)%")),
        ("u_over_i_pct", re.compile(r"\|U\|/I\s*=\s*([-+]?\d*\.?\d+)%")),
        (
            "l_over_i_pct",
            re.compile(r"(?:√\(Q²\+U²\)|sqrt\(Q\^2\+U\^2\))\/I\s*=\s*([-+]?\d*\.?\d+)%"),
        ),
        ("v_over_i_pct", re.compile(r"\|V\|/I\s*=\s*([-+]?\d*\.?\d+)%")),
    ]

    signed_patterns = [
        (
            "q_over_i_signed_pct",
            "q_over_i_mad_pct",
            re.compile(r"Q/I\s*=\s*([-+]?\d*\.?\d+)%\s*±\s*([-+]?\d*\.?\d+)%"),
        ),
        (
            "u_over_i_signed_pct",
            "u_over_i_mad_pct",
            re.compile(r"U/I\s*=\s*([-+]?\d*\.?\d+)%\s*±\s*([-+]?\d*\.?\d+)%"),
        ),
        (
            "l_over_i_signed_pct",
            "l_over_i_mad_pct",
            re.compile(r"(?:√\(Q²\+U²\)|sqrt\(Q\^2\+U\^2\))/I\s*=\s*([-+]?\d*\.?\d+)%\s*±\s*([-+]?\d*\.?\d+)%"),
        ),
        (
            "v_over_i_signed_pct",
            "v_over_i_mad_pct",
            re.compile(r"V/I\s*=\s*([-+]?\d*\.?\d+)%\s*±\s*([-+]?\d*\.?\d+)%"),
        ),
    ]

    try:
        lines = txt_path.read_text(errors="replace").splitlines()
    except Exception as exc:
        return metrics, False, f"read_failed:{exc}"

    for line in lines[:120]:
        for key, pattern in patterns:
            if metrics[key] is not None:
                continue
            match = pattern.search(line)
            if match:
                metrics[key] = float(match.group(1))

        for val_key, mad_key, pattern in signed_patterns:
            if metrics[val_key] is not None and metrics[mad_key] is not None:
                continue
            match = pattern.search(line)
            if match:
                metrics[val_key] = float(match.group(1))
                metrics[mad_key] = float(match.group(2))

    channel_row_pattern = re.compile(r"^\s*\d+\s+[-+]?\d")
    metrics["channel_count_detected"] = sum(1 for line in lines if channel_row_pattern.match(line))

    parse_ok = all(value is not None for value in metrics.values())
    error = "" if parse_ok else "missing_leakage_stat"
    return metrics, parse_ok, error


def find_footprint_file(metadata_dir: Path, sb_ref: str):
    matches = sorted(metadata_dir.glob(f"footprintOutput-sb{sb_ref}-*.txt"))
    if matches:
        return matches[0]
    fallback = sorted(metadata_dir.glob("footprintOutput-*.txt"))
    return fallback[0] if fallback else None


def find_assessment_file(assessment_dir: Path, beam: int, variant: str):
    beam_tag = f"beam{beam:02d}"
    if variant == "bpcal":
        candidates = sorted(
            path
            for path in assessment_dir.glob(f"*.{beam_tag}.txt")
            if not path.name.endswith(".lcal.txt")
        )
    else:
        candidates = sorted(assessment_dir.glob(f"*.{beam_tag}.lcal.txt"))

    return candidates[0] if candidates else None


def main():
    parser = argparse.ArgumentParser(description="Build Phase-1 leakage master table for MVP subset")
    parser.add_argument(
        "--manifest",
        default="projects/calibration-updates-2026/manifests/sb_manifest_reffield_average.txt",
        help="Manifest file path",
    )
    parser.add_argument(
        "--local-base",
        default=str(Path.home() / "DATA" / "reffield-average"),
        help="Local base containing tuple directories",
    )
    parser.add_argument("--start-index", type=int, default=14)
    parser.add_argument("--end-index",   type=int, default=42)
    parser.add_argument("--exclude-indices", default="24-29")
    parser.add_argument(
        "--output-csv",
        default=str(Path.home() / "DATA" / "reffield-average" / "leakage_master_table.csv"),
        help="Output CSV path",
    )
    parser.add_argument(
        "--output-summary",
        default=str(Path.home() / "DATA" / "reffield-average" / "phase1_mvp_extraction_summary.md"),
        help="Output markdown summary path",
    )
    parser.add_argument(
        "--pitch-residual-tolerance-deg",
        type=float,
        default=0.02,
        help="Absolute tolerance for pitch sanity pass/fail",
    )
    args = parser.parse_args()

    manifest_path = Path(args.manifest)
    local_base = Path(args.local_base)
    output_csv = Path(args.output_csv)
    output_summary = Path(args.output_summary)

    exclude_ranges = parse_exclude_indices(args.exclude_indices)
    tuples = parse_manifest_rows(manifest_path, args.start_index, args.end_index, exclude_ranges)

    output_csv.parent.mkdir(parents=True, exist_ok=True)
    output_summary.parent.mkdir(parents=True, exist_ok=True)

    output_rows = []

    tuple_count = len(tuples)
    tuples_with_pitch = 0
    tuples_with_footprint = 0
    tuples_pitch_sanity_pass = 0

    for tuple_info in tuples:
        tuple_rel = tuple_info["tuple_rel_path"]
        tuple_dir = local_base / tuple_rel
        if not tuple_dir.exists():
            print(f"  Skipping {tuple_rel!r}: local directory not found")
            continue
        metadata_dir = tuple_dir / "metadata"
        assessment_dir = tuple_dir / f"1934-processing-SB-{tuple_info['sb_target_1934']}" / "assessment_results"

        footprint_name = parse_footprint_name(metadata_dir, tuple_info["sb_ref"])
        obs_meta = parse_obs_metadata(metadata_dir, tuple_info["sb_ref"])
        pitch_deg, pitch_source_file = parse_pitch_deg(metadata_dir, tuple_info["sb_ref"])
        if pitch_deg is not None:
            tuples_with_pitch += 1

        footprint_file = find_footprint_file(metadata_dir, tuple_info["sb_ref"])
        beam_map = parse_footprint(footprint_file) if footprint_file else {}
        if beam_map:
            tuples_with_footprint += 1

        offset_nn_spacing_deg = compute_offset_nn_spacing(beam_map) if beam_map else None
        pitch_spacing_residual_deg = None
        pitch_sanity_pass = None

        if pitch_deg is not None and offset_nn_spacing_deg is not None:
            pitch_spacing_residual_deg = offset_nn_spacing_deg - pitch_deg
            pitch_sanity_pass = abs(pitch_spacing_residual_deg) <= args.pitch_residual_tolerance_deg
            if pitch_sanity_pass:
                tuples_pitch_sanity_pass += 1

        for beam in range(36):
            footprint = beam_map.get(
                beam,
                {
                    "offset_x_deg": None,
                    "offset_y_deg": None,
                    "beam_centre_ra_hms": "",
                    "beam_centre_dec_dms": "",
                    "beam_centre_ra_deg": None,
                    "beam_centre_dec_deg": None,
                },
            )

            for variant in ["bpcal", "lcal"]:
                assessment_file = find_assessment_file(assessment_dir, beam, variant)

                if assessment_file is None:
                    metrics = {
                        "q_over_i_pct": None,
                        "u_over_i_pct": None,
                        "l_over_i_pct": None,
                        "v_over_i_pct": None,
                        "q_over_i_signed_pct": None,
                        "u_over_i_signed_pct": None,
                        "l_over_i_signed_pct": None,
                        "v_over_i_signed_pct": None,
                        "q_over_i_mad_pct": None,
                        "u_over_i_mad_pct": None,
                        "l_over_i_mad_pct": None,
                        "v_over_i_mad_pct": None,
                        "channel_count_detected": 0,
                    }
                    parse_ok = False
                    parse_error = "assessment_file_missing"
                    assessment_file_str = ""
                else:
                    metrics, parse_ok, parse_error = parse_leakage_metrics(assessment_file)
                    assessment_file_str = str(assessment_file)

                output_rows.append(
                    {
                        "manifest_index": tuple_info["manifest_index"],
                        "sb_ref": tuple_info["sb_ref"],
                        "ref_fieldname": tuple_info["ref_fieldname"],
                        "sb_1934": tuple_info["sb_1934"],
                        "sb_holo": tuple_info["sb_holo"],
                        "sb_target_1934": tuple_info["sb_target_1934"],
                        "odc_weight": tuple_info["odc_weight"],
                        "amp_strategy": tuple_info["amp_strategy"],
                        "do_preflag_reftable": tuple_info["do_preflag_reftable"],
                        "tuple_rel_path": tuple_rel,
                        "metadata_dir": str(metadata_dir),
                        "assessment_dir": str(assessment_dir),
                        "variant": variant,
                        "beam": beam,
                        "beam_centre_ra_hms": footprint["beam_centre_ra_hms"],
                        "beam_centre_dec_dms": footprint["beam_centre_dec_dms"],
                        "beam_centre_ra_deg": footprint["beam_centre_ra_deg"],
                        "beam_centre_dec_deg": footprint["beam_centre_dec_deg"],
                        "offset_x_deg": footprint["offset_x_deg"],
                        "offset_y_deg": footprint["offset_y_deg"],
                        "pitch_deg_from_schedblock": pitch_deg,
                        "pitch_source_file": pitch_source_file,
                        "offset_nn_spacing_deg": offset_nn_spacing_deg,
                        "pitch_spacing_residual_deg": pitch_spacing_residual_deg,
                        "pitch_sanity_tolerance_deg": args.pitch_residual_tolerance_deg,
                        "pitch_sanity_pass": pitch_sanity_pass,
                        "footprint_name": footprint_name,
                        "footprint_file": str(footprint_file) if footprint_file else "",
                        "weights_id":              obs_meta["weights_id"],
                        "centre_freq_mhz":         obs_meta["centre_freq_mhz"],
                        "footprint_rotation_deg":  obs_meta["footprint_rotation_deg"],
                        "pol_axis_deg":             obs_meta["pol_axis_deg"],
                        "leak_q_over_i_pct": metrics["q_over_i_pct"],
                        "leak_u_over_i_pct": metrics["u_over_i_pct"],
                        "leak_l_over_i_pct": metrics["l_over_i_pct"],
                        "leak_v_over_i_pct": metrics["v_over_i_pct"],
                        "leak_q_over_i_signed_pct": metrics["q_over_i_signed_pct"],
                        "leak_u_over_i_signed_pct": metrics["u_over_i_signed_pct"],
                        "leak_l_over_i_signed_pct": metrics["l_over_i_signed_pct"],
                        "leak_v_over_i_signed_pct": metrics["v_over_i_signed_pct"],
                        "leak_q_over_i_mad_pct": metrics["q_over_i_mad_pct"],
                        "leak_u_over_i_mad_pct": metrics["u_over_i_mad_pct"],
                        "leak_l_over_i_mad_pct": metrics["l_over_i_mad_pct"],
                        "leak_v_over_i_mad_pct": metrics["v_over_i_mad_pct"],
                        "channel_count_detected": metrics["channel_count_detected"],
                        "assessment_txt_file": assessment_file_str,
                        "leakage_parse_ok": parse_ok,
                        "leakage_parse_error": parse_error,
                    }
                )

    fieldnames = [
        "manifest_index",
        "sb_ref",
        "ref_fieldname",
        "sb_1934",
        "sb_holo",
        "sb_target_1934",
        "odc_weight",
        "amp_strategy",
        "do_preflag_reftable",
        "tuple_rel_path",
        "metadata_dir",
        "assessment_dir",
        "variant",
        "beam",
        "beam_centre_ra_hms",
        "beam_centre_dec_dms",
        "beam_centre_ra_deg",
        "beam_centre_dec_deg",
        "offset_x_deg",
        "offset_y_deg",
        "pitch_deg_from_schedblock",
        "pitch_source_file",
        "offset_nn_spacing_deg",
        "pitch_spacing_residual_deg",
        "pitch_sanity_tolerance_deg",
        "pitch_sanity_pass",
        "footprint_name",
        "footprint_file",
        "weights_id",
        "centre_freq_mhz",
        "footprint_rotation_deg",
        "pol_axis_deg",
        "leak_q_over_i_pct",
        "leak_u_over_i_pct",
        "leak_l_over_i_pct",
        "leak_v_over_i_pct",
        "leak_q_over_i_signed_pct",
        "leak_u_over_i_signed_pct",
        "leak_l_over_i_signed_pct",
        "leak_v_over_i_signed_pct",
        "leak_q_over_i_mad_pct",
        "leak_u_over_i_mad_pct",
        "leak_l_over_i_mad_pct",
        "leak_v_over_i_mad_pct",
        "channel_count_detected",
        "assessment_txt_file",
        "leakage_parse_ok",
        "leakage_parse_error",
    ]

    output_rows.sort(key=lambda row: (row["manifest_index"], row["beam"], row["variant"]))

    with output_csv.open("w", newline="") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(output_rows)

    total_rows = len(output_rows)
    expected_rows = tuple_count * 36 * 2
    parsed_rows = sum(1 for row in output_rows if row["leakage_parse_ok"])

    summary_lines = [
        "# Phase-1 MVP Extraction Summary",
        "",
        f"- Manifest: {manifest_path}",
        f"- Local base: {local_base}",
        f"- Selected tuple count: {tuple_count}",
        f"- Expected row count (tuple x beam x variant): {expected_rows}",
        f"- Output row count: {total_rows}",
        f"- Leakage parse OK rows: {parsed_rows}/{total_rows}",
        f"- Tuples with pitch parsed: {tuples_with_pitch}/{tuple_count}",
        f"- Tuples with footprint parsed: {tuples_with_footprint}/{tuple_count}",
        f"- Tuples with pitch sanity pass: {tuples_pitch_sanity_pass}/{tuple_count}",
        f"- Pitch residual tolerance (deg): {args.pitch_residual_tolerance_deg}",
        f"- Output CSV: {output_csv}",
    ]

    output_summary.write_text("\n".join(summary_lines) + "\n")

    print(f"Wrote {output_csv}")
    print(f"Wrote {output_summary}")
    print(
        "SUMMARY "
        f"tuples={tuple_count} "
        f"rows={total_rows} "
        f"parse_ok={parsed_rows} "
        f"pitch_ok={tuples_pitch_sanity_pass}/{tuple_count}"
    )


if __name__ == "__main__":
    main()
