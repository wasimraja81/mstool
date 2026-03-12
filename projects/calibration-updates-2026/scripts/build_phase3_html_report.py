#!/usr/bin/env python3

import argparse
import csv
import html
import shutil
from pathlib import Path
from urllib.parse import quote


def read_csv(path: Path):
    with path.open() as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, rows, fieldnames):
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def to_float(value, default=-1e18):
    try:
        return float(value)
    except Exception:
        return default


def fmt_num(value, digits=3):
    if value is None:
        return ""
    try:
        number = float(value)
    except Exception:
        return str(value)
    text = f"{number:.{digits}f}"
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text


def build_html_table(rows, headers, labels, max_rows=12):
    shown = rows[:max_rows]
    thead = "".join(f"<th>{html.escape(labels.get(h, h))}</th>" for h in headers)
    body_rows = []
    for row in shown:
        rendered = []
        for h in headers:
            v = row.get(h, "")
            if h in {
                "delta_to_beam_baseline",
                "delta_to_beam_baseline_f",
                "delta_to_beam_baseline_o",
                "p95_l_over_i",
                "robust_z",
                "beam_median_l_over_i",
                "beam_mean_l_over_i",
                "beam_mad_l_over_i",
                "beam_min_l_over_i",
                "beam_max_l_over_i",
            }:
                v = fmt_num(v, digits=3)
            elif h in {"affected_beam_count", "affected_beam_count_f", "affected_beam_count_o", "n_candidates"}:
                v = fmt_num(v, digits=0)
            rendered.append(f"<td>{html.escape(str(v))}</td>")
        cells = "".join(rendered)
        body_rows.append(f"<tr>{cells}</tr>")
    tbody = "\n".join(body_rows) if body_rows else "<tr><td colspan='100%'>No rows</td></tr>"
    return f"<table><thead><tr>{thead}</tr></thead><tbody>{tbody}</tbody></table>"


def top_n(rows, variant, n=5):
    filtered = [r for r in rows if r.get("variant") == variant]

    def delta_value(row):
        return to_float(
            row.get("delta_to_beam_baseline_f", row.get("delta_to_beam_baseline_o", row.get("delta_to_beam_baseline"))),
            default=0,
        )

    def affected_value(row):
        return to_float(
            row.get("affected_beam_count_f", row.get("affected_beam_count_o", row.get("affected_beam_count"))),
            default=0,
        )

    filtered.sort(
        key=lambda r: (
            to_float(r.get("p95_l_over_i")),
            affected_value(r),
            delta_value(r),
        ),
        reverse=True,
    )
    return filtered[:n]


def localize_plot_links(rows, tables_dir: Path, asset_root: Path, asset_http_base: str):
    for row in rows:
        raw = row.get("sb_ref_plot_links", "")
        if not raw:
            continue
        localized = []
        for token in str(raw).split(";"):
            if not token:
                continue
            if "|" in token:
                sb_ref, src_path = token.split("|", 1)
            else:
                sb_ref, src_path = token, ""
            src_path = src_path.strip()
            if not src_path:
                localized.append(f"{sb_ref}|")
                continue
            src = Path(src_path)
            if src.exists() and src.is_file():
                try:
                    resolved = src.resolve()
                    if resolved.is_relative_to(asset_root):
                        rel = resolved.relative_to(asset_root).as_posix()
                        uri = f"{asset_http_base.rstrip('/')}/{quote(rel, safe='/')}"
                    else:
                        uri = resolved.as_uri()
                except Exception:
                    uri = src_path
                localized.append(f"{sb_ref}|{uri}")
            else:
                localized.append(f"{sb_ref}|")
        row["sb_ref_plot_links"] = ";".join(localized)


def build_summary_table(rows, plots_dir=None):
    """Render an inline HTML table with 9 summary columns and clickable SB_REF links.

    If plots_dir is given, the reference-field cell links to the individual
    footprint PNG for that (field, ODC, variant) combination.
    """
    headers = [
        "odc_weight", "variant", "ref_fieldname", "n_candidates",
        "sb_ref_values", "beam_median_l_over_i", "beam_mad_l_over_i",
        "beam_min_l_over_i", "beam_max_l_over_i",
    ]
    labels = {
        "odc_weight": "ODC weight",
        "variant": "Variant",
        "ref_fieldname": "Reference field",
        "n_candidates": "n_obs(f)",
        "sb_ref_values": "Observed SB_REF IDs",
        "beam_median_l_over_i": "μ⁽ᵇ⁾",
        "beam_mad_l_over_i": "MAD⁽ᵇ⁾",
        "beam_min_l_over_i": "min⁽ᵇ⁾",
        "beam_max_l_over_i": "max⁽ᵇ⁾",
    }
    numeric_cols = {
        "beam_median_l_over_i", "beam_mad_l_over_i",
        "beam_min_l_over_i", "beam_max_l_over_i",
    }
    thead = "".join(f"<th>{html.escape(labels.get(h, h))}</th>" for h in headers)
    body_rows = []
    for row in rows:
        cells = []
        for h in headers:
            v = row.get(h, "")
            if h == "ref_fieldname" and plots_dir is not None:
                # Link to individual footprint PNG
                field_safe = str(v).replace("/", "_")
                odc = row.get("odc_weight", "")
                vtag = str(row.get("variant", ""))  # "regular" or "lcal"
                png_name = f"footprint_dL_{field_safe}_odc{odc}_{vtag}.png"
                if (plots_dir / png_name).exists():
                    href = f"plots/{quote(png_name)}"
                    cells.append(
                        f"<td><a href='{html.escape(href)}' target='_blank'"
                        f" rel='noopener'>{html.escape(str(v))}</a></td>"
                    )
                else:
                    cells.append(f"<td>{html.escape(str(v))}</td>")
            elif h == "sb_ref_values":
                plot_raw = row.get("sb_ref_plot_links", "")
                plot_map = {}
                if plot_raw:
                    for part in str(plot_raw).split(";"):
                        if not part:
                            continue
                        pieces = part.split("|", 1)
                        sb = pieces[0].strip()
                        link = pieces[1].strip() if len(pieces) > 1 else ""
                        if sb:
                            plot_map[sb] = link
                parts = [p.strip() for p in str(v).split(";") if p.strip()]
                link_parts = []
                for sb in parts:
                    link = plot_map.get(sb, "")
                    if link:
                        link_parts.append(
                            f"<a href='{html.escape(link)}' target='_self'"
                            f" rel='noopener'>SB_REF-{html.escape(sb)}</a>"
                        )
                    else:
                        link_parts.append(f"SB_REF-{html.escape(sb)}")
                cells.append(f"<td>{' ; '.join(link_parts)}</td>")
            elif h in numeric_cols:
                cells.append(f"<td>{html.escape(fmt_num(v, digits=3))}</td>")
            elif h == "n_candidates":
                cells.append(f"<td>{html.escape(fmt_num(v, digits=0))}</td>")
            else:
                cells.append(f"<td>{html.escape(str(v))}</td>")
        body_rows.append(f"<tr>{''.join(cells)}</tr>")
    if not body_rows:
        tbody = "<tr><td colspan='9'>No rows</td></tr>"
    else:
        tbody = "\n".join(body_rows)
    return f"<table><thead><tr>{thead}</tr></thead><tbody>{tbody}</tbody></table>"


def write_csv_viewer(output_dir: Path, csv_filename: str, title: str, column_help):
        viewer_path = output_dir / f"view_{csv_filename}.html"
        help_rows = "".join(
                f"<tr><td>{html.escape(col)}</td><td>{html.escape(desc)}</td></tr>"
                for col, desc in column_help
        )

        score_explainer = ""
        delta_header_label = "ΔL"
        affected_header_label = "N+"
        cand_sym = "c"  # default; overridden for score pages
        if "effect_scores" in csv_filename:
            is_field_mode = "field_effect_scores" in csv_filename
            if is_field_mode:
                mode_label = "field effects at fixed ODC"
                comparison_group = "fixed ODC weight + variant (regular or lcal)"
                candidate_axis = "reference fields"
                fixed_axis_note = "On this page we do not compare across ODCs; ODC is fixed within each group."
                delta_header_label = "ΔL_f"
                delta_phrase = "ΔL_f"
                affected_header_label = "N+_f"
                candidate_note = "Here each row/candidate is a reference field (sky position)."
                cand_sym = "f"  # TeX symbol for candidate
                cand_label = "reference field (sky position)"
                fixed_sym = "o"
                fixed_label = "ODC weight"
            else:
                mode_label = "ODC effects at fixed field"
                comparison_group = "fixed reference field + variant (regular or lcal)"
                candidate_axis = "ODC weights"
                fixed_axis_note = "On this page we do not compare across fields; reference field is fixed within each group."
                delta_header_label = "ΔL_o"
                delta_phrase = "ΔL_o"
                affected_header_label = "N+_o"
                candidate_note = "Here each row/candidate is an ODC weight."
                cand_sym = "o"
                cand_label = "ODC weight"
                fixed_sym = "f"
                fixed_label = "reference field (sky position)"

            score_explainer = f"""
    <h2>Interpretation Guide</h2>
        <p class='meta'>This score table summarizes {html.escape(mode_label)} using robust (median/MAD-based) statistics.</p>
    <h4>Notation convention</h4>
    <p class='meta'>We use \\(\\mu\\) for the median throughout. Subscripts = <em>free indices</em> (what the result depends on). Superscript = <em>dimension aggregated over</em>.</p>
    <p class='meta'><b>Index definitions on this page:</b> \\({cand_sym}\\) = {html.escape(cand_label)} (candidate, one row); \\(b\\) = beam; \\(s\\) = SB_REF observation. Fixed axis: \\({fixed_sym}\\) = {html.escape(fixed_label)}.</p>
    <ul>
        <li><b>Current comparison group:</b> {html.escape(comparison_group)}.</li>
        <li><b>Candidate axis in this table:</b> {html.escape(candidate_axis)} inside the current comparison group.</li>
        <li><b>Candidate note:</b> {html.escape(candidate_note)}</li>
        <li><b>Beam-candidate statistic:</b> \\(\\mu_{{b,{cand_sym}}}^{{(s)}}\\) = median of dL over SB_REF samples \\(s\\), for beam \\(b\\) and candidate \\({cand_sym}\\).</li>
        <li><b>Per-beam baseline:</b> \\(\\mu_b^{{({cand_sym})}} = \\text{{median over }} {cand_sym} \\text{{ of }} \\mu_{{b,{cand_sym}}}^{{(s)}}\\), i.e., median across candidates in the same comparison group.</li>
        <li><b>Residual:</b> \\(\\Delta_{{b,{cand_sym}}} = \\mu_{{b,{cand_sym}}}^{{(s)}} - \\mu_b^{{({cand_sym})}}\\).</li>
        <li><b>{html.escape(delta_phrase)}:</b> \\(\\Delta L_{cand_sym} = \\mu^{{(b)}}(\\Delta_{{b,{cand_sym}}})\\), i.e., median residual over beams (positive \\(\\Rightarrow\\) candidate tends worse relative to in-group beam baseline).</li>
        <li><b>{html.escape(affected_header_label)}:</b> number of beams where \\(\\Delta_{{b,{cand_sym}}} > 0\\).</li>
        <li><b>p95_l_over_i:</b> 95th percentile of dL (high-tail risk indicator).</li>
        <li><b>robust_z:</b> normalized score against peers in the same group using median/MAD.</li>
    </ul>
    <h3>Symbol Legend</h3>
    <ul>
        <li><b>\\(\\mu_{{b,{cand_sym}}}^{{(s)}}\\)</b>: median dL over SB_REF samples for beam \\(b\\), candidate \\({cand_sym}\\).</li>
        <li><b>\(\mu^{{(b)}}\)</b>: median across beams of \(\mu_{{b,{cand_sym}}}^{{(s)}}\).</li>
        <li><b>MAD\(^{{(b)}}\)</b>: MAD across beams of \(\mu_{{b,{cand_sym}}}^{{(s)}}\).</li>
        <li><b>min\(^{{(b)}}\)</b>, <b>max\(^{{(b)}}\)</b>: beam-wise min/max of \(\mu_{{b,{cand_sym}}}^{{(s)}}\).</li>
        <li><b>n_obs({cand_sym})</b>: number of unique SB_REF observations for candidate \({cand_sym}\).</li>
        <li><b>{html.escape(affected_header_label)}</b>: number of beams where \(\Delta_{{b,{cand_sym}}} > 0\).</li>
        <li><b>P95\(^{{(b)}}\)</b>: 95th percentile across beams of \(\mu_{{b,{cand_sym}}}^{{(s)}}\).</li>
    </ul>
    <h4>Note on the raw statistic</h4>
    <p class='meta'>The raw beam-candidate value \\(\\mu_{{b,{cand_sym}}}^{{(s)}}\\) is numerically identical across field-effect and ODC-effect pages for the same (beam, field, ODC) tuple, because the underlying SB_REF samples are the same. What differs between pages is the <em>baseline</em> (median over \\({cand_sym}\\) vs the other axis) and therefore the <em>residual</em> and final score.</p>
        <p class='meta'>{html.escape(fixed_axis_note)}</p>
        <p class='meta'>Quick read: higher <b>\\(\\Delta L_{cand_sym}\\)</b> + higher <b>{html.escape(affected_header_label)}</b> + high <b>P95(dL)</b> suggests a stronger candidate effect.</p>
"""
        page = f"""<!doctype html>
<html lang='en'>
<head>
    <meta charset='utf-8' />
    <meta name='viewport' content='width=device-width, initial-scale=1' />
    <title>{html.escape(title)}</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; line-height: 1.4; }}
        table {{ border-collapse: collapse; width: 100%; font-size: 12px; margin-top: 12px; }}
        th, td {{ border: 1px solid #ccc; padding: 6px 8px; text-align: left; }}
        th {{ background: #f3f3f3; position: sticky; top: 0; }}
        .meta {{ color: #444; font-size: 13px; margin-bottom: 10px; }}
    </style>
    <script>
        window.MathJax = {{
            tex: {{ inlineMath: [['\\\\(','\\\\)']] }},
            svg: {{ fontCache: 'global' }}
        }};
    </script>
    <script defer src="https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-svg.js"></script>
</head>
<body>
    <h1>{html.escape(title)}</h1>
    <p class='meta'>Loaded from CSV in this folder. Opened as HTML for easier browser viewing.</p>

    {score_explainer}

    <h2>Column legend</h2>
    <table>
        <thead><tr><th>Column</th><th>Meaning</th></tr></thead>
        <tbody>{help_rows}</tbody>
    </table>

    <h2>Data</h2>
    <p class='meta'>All statistics below are over percentage linear polarisation leakage, dL (%).</p>
    <table id='grid'></table>

    <script>
        async function load() {{
            const csvName = {repr(csv_filename)};
            const sep = csvName.includes('?') ? '&' : '?';
            const res = await fetch(csvName + sep + 'v=' + Date.now());
            const text = await res.text();
            const normalized = text.split(String.fromCharCode(13)).join('');
            const lines = normalized.split(String.fromCharCode(10)).filter(Boolean);
            if (!lines.length) return;
            const headers = lines[0].split(',');
            const headerLabelMap = {{
                'delta_to_beam_baseline': {repr(delta_header_label)},
                'delta_to_beam_baseline_f': 'ΔL_f',
                'delta_to_beam_baseline_o': 'ΔL_o',
                'n_candidates': 'n_obs({cand_sym})',
                'beam_median_l_over_i': 'μ⁽ᵇ⁾',
                'beam_mean_l_over_i': '(hidden)',
                'beam_mad_l_over_i': 'MAD⁽ᵇ⁾',
                'beam_min_l_over_i': 'min⁽ᵇ⁾',
                'beam_max_l_over_i': 'max⁽ᵇ⁾',
                'affected_beam_count': {repr(affected_header_label)},
                'affected_beam_count_f': 'N+_f',
                'affected_beam_count_o': 'N+_o',
                'p95_l_over_i': 'P95⁽ᵇ⁾'
            }};
            const hiddenHeaders = new Set(['sb_ref_plot_links', 'beam_mean_l_over_i']);
            const visibleHeaders = headers.filter(h => !hiddenHeaders.has(h));
            const rows = lines.slice(1).map(line => line.split(','));

            const grid = document.getElementById('grid');
            const thead = document.createElement('thead');
            const trh = document.createElement('tr');
            visibleHeaders.forEach(h => {{
                const th = document.createElement('th');
                th.textContent = headerLabelMap[h] || h;
                trh.appendChild(th);
            }});
            thead.appendChild(trh);
            grid.appendChild(thead);

            const tbody = document.createElement('tbody');
            rows.forEach(r => {{
                const tr = document.createElement('tr');
                const plotLinksIndex = headers.indexOf('sb_ref_plot_links');
                const plotRaw = plotLinksIndex >= 0 ? (r[plotLinksIndex] ?? '') : '';
                const plotLookup = {{}};
                if (plotRaw !== '') {{
                    String(plotRaw).split(';').filter(Boolean).forEach(part => {{
                        const pieces = part.split('|');
                        const sb = (pieces[0] || '').trim();
                        const link = pieces.length > 1 ? (pieces[1] || '').trim() : '';
                        if (sb) plotLookup[sb] = link;
                    }});
                }}

                visibleHeaders.forEach((h) => {{
                    const i = headers.indexOf(h);
                    const td = document.createElement('td');
                    let v = r[i] ?? '';
                    const num = Number(v);
                    if (h === 'sb_ref_values' && v !== '') {{
                        const parts = String(v).split(';').filter(Boolean);
                        if (!parts.length) {{
                            td.textContent = '';
                        }} else {{
                            parts.forEach((sbRaw, idx) => {{
                                const sb = String(sbRaw).trim();
                                const link = plotLookup[sb] || '';
                                if (idx > 0) td.appendChild(document.createTextNode(' ; '));
                                if (link) {{
                                    const a = document.createElement('a');
                                    a.href = link;
                                    a.target = '_self';
                                    a.rel = 'noopener';
                                    a.textContent = `SB_REF-${{sb}}`;
                                    a.addEventListener('click', (ev) => {{
                                        ev.preventDefault();
                                        window.location.href = link;
                                    }});
                                    td.appendChild(a);
                                }} else {{
                                    td.appendChild(document.createTextNode(`SB_REF-${{sb}} (missing)`));
                                }}
                            }});
                        }}
                    }} else if (!Number.isNaN(num) && v !== '') {{
                        v = num.toFixed(3).replace(/\.0+$/, '').replace(/(\.\d*[1-9])0+$/, '$1');
                        td.textContent = v;
                    }} else {{
                        td.textContent = v;
                    }}
                    tr.appendChild(td);
                }});
                tbody.appendChild(tr);
            }});
            grid.appendChild(tbody);
        }}
        load();
    </script>
</body>
</html>
"""
        viewer_path.write_text(page)
        return viewer_path


def main():
    parser = argparse.ArgumentParser(description="Build Phase-3 HTML index report for MVP outputs")
    parser.add_argument(
        "--data-root",
        default=str(Path.home() / "DATA" / "reffield-average"),
        help="Top-level data directory containing phase1/phase2 outputs",
    )
    parser.add_argument(
        "--phase2-dir",
        default=None,
        help="Optional explicit Phase-2 directory (defaults to <data-root>/phase2)",
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        help="Optional explicit Phase-3 output directory (defaults to <data-root>/phase3)",
    )
    parser.add_argument(
        "--asset-root",
        default=str(Path.home()),
        help="Filesystem root exposed by local HTTP server for plot links (default: $HOME)",
    )
    parser.add_argument(
        "--asset-http-base",
        default="http://127.0.0.1:8767",
        help="HTTP base URL used to convert absolute plot paths into clickable links",
    )
    args = parser.parse_args()

    data_root = Path(args.data_root)
    phase2_dir = Path(args.phase2_dir) if args.phase2_dir else data_root / "phase2"
    output_dir = Path(args.output_dir) if args.output_dir else data_root / "phase3"
    asset_root = Path(args.asset_root)
    asset_http_base = args.asset_http_base
    tables_dir = output_dir / "tables"

    output_dir.mkdir(parents=True, exist_ok=True)
    tables_dir.mkdir(parents=True, exist_ok=True)

    inputs = {
        "beam_x_field_at_fixed_odc.csv": phase2_dir / "beam_x_field_at_fixed_odc.csv",
        "field_effect_scores_at_fixed_odc.csv": phase2_dir / "field_effect_scores_at_fixed_odc.csv",
        "beam_x_odc_at_fixed_field.csv": phase2_dir / "beam_x_odc_at_fixed_field.csv",
        "odc_effect_scores_at_fixed_field.csv": phase2_dir / "odc_effect_scores_at_fixed_field.csv",
        "phase2_mvp_summary.md": phase2_dir / "phase2_mvp_summary.md",
    }

    missing = [name for name, path in inputs.items() if not path.exists()]
    if missing:
        raise FileNotFoundError(f"Missing Phase-2 input files: {', '.join(missing)}")

    copied_paths = {}
    for name, src in inputs.items():
        dst = tables_dir / name
        shutil.copy2(src, dst)
        copied_paths[name] = dst

    # ── Read data ────────────────────────────────────────────────────────
    field_scores = read_csv(copied_paths["field_effect_scores_at_fixed_odc.csv"])
    beam_x_field = read_csv(copied_paths["beam_x_field_at_fixed_odc.csv"])
    beam_x_odc = read_csv(copied_paths["beam_x_odc_at_fixed_field.csv"])

    localize_plot_links(field_scores, tables_dir, asset_root, asset_http_base)

    # ── Split beam-level tables by variant ──────────────────────────────
    for stem, rows in [
        ("beam_x_field_at_fixed_odc", beam_x_field),
        ("beam_x_odc_at_fixed_field", beam_x_odc),
    ]:
        if not rows:
            continue
        fieldnames = list(rows[0].keys())
        for variant in ["regular", "lcal"]:
            filtered = [r for r in rows if r.get("variant") == variant]
            write_csv(tables_dir / f"{stem}.{variant}.csv", filtered, fieldnames)

    # ── Inline summary tables (regular / lcal) ─────────────────────────
    field_regular = [r for r in field_scores if r.get("variant") == "regular"]
    field_lcal = [r for r in field_scores if r.get("variant") == "lcal"]

    # ── Footprint heatmap links (one PNG per unique field) ──────────────
    plots_dir = output_dir / "plots"
    unique_fields = sorted({r.get("ref_fieldname", "") for r in field_scores} - {""})
    footprint_links = []
    for fname in unique_fields:
        safe = fname.replace("/", "_")
        png = f"footprint_dL_{safe}.png"
        if (plots_dir / png).exists():
            footprint_links.append(
                f"<li><a href='plots/{quote(png)}' target='_blank' rel='noopener'>{html.escape(fname)}</a></li>"
            )
    footprint_links_html = f"<ul>{''.join(footprint_links)}</ul>" if footprint_links else "<p class='meta'>No footprint plots found.</p>"

    # ── Build beam-level CSV viewer pages ───────────────────────────────
    beam_viewer_specs = {
        "beam_x_field_at_fixed_odc.regular.csv": (
            "Beam-by-field table at fixed ODC (regular)",
            [
                ("odc_weight", "ODC setting"),
                ("variant", "regular or lcal"),
                ("beam", "beam index 0-35"),
                ("ref_fieldname", "reference calibration field"),
                ("median_l_over_i", "median L/I [%]"),
                ("p90_l_over_i", "90th percentile L/I [%]"),
                ("count_sb_ref", "number of SB_REF observations"),
                ("count_samples", "total sample count"),
            ],
        ),
        "beam_x_field_at_fixed_odc.lcal.csv": (
            "Beam-by-field table at fixed ODC (lcal)",
            [
                ("odc_weight", "ODC setting"),
                ("variant", "regular or lcal"),
                ("beam", "beam index 0-35"),
                ("ref_fieldname", "reference calibration field"),
                ("median_l_over_i", "median L/I [%]"),
                ("p90_l_over_i", "90th percentile L/I [%]"),
                ("count_sb_ref", "number of SB_REF observations"),
                ("count_samples", "total sample count"),
            ],
        ),
        "beam_x_odc_at_fixed_field.regular.csv": (
            "Beam-by-ODC table at fixed field (regular)",
            [
                ("ref_fieldname", "reference calibration field"),
                ("variant", "regular or lcal"),
                ("beam", "beam index 0-35"),
                ("odc_weight", "ODC setting"),
                ("median_l_over_i", "median L/I [%]"),
                ("p90_l_over_i", "90th percentile L/I [%]"),
                ("count_sb_ref", "number of SB_REF observations"),
                ("count_samples", "total sample count"),
            ],
        ),
        "beam_x_odc_at_fixed_field.lcal.csv": (
            "Beam-by-ODC table at fixed field (lcal)",
            [
                ("ref_fieldname", "reference calibration field"),
                ("variant", "regular or lcal"),
                ("beam", "beam index 0-35"),
                ("odc_weight", "ODC setting"),
                ("median_l_over_i", "median L/I [%]"),
                ("p90_l_over_i", "90th percentile L/I [%]"),
                ("count_sb_ref", "number of SB_REF observations"),
                ("count_samples", "total sample count"),
            ],
        ),
    }

    beam_links = []
    for csv_name in [
        "beam_x_field_at_fixed_odc.regular.csv",
        "beam_x_field_at_fixed_odc.lcal.csv",
        "beam_x_odc_at_fixed_field.regular.csv",
        "beam_x_odc_at_fixed_field.lcal.csv",
    ]:
        if not (tables_dir / csv_name).exists():
            continue
        title, col_help = beam_viewer_specs[csv_name]
        viewer = write_csv_viewer(tables_dir, csv_name, title, col_help)
        beam_links.append(
            f"<li>{html.escape(csv_name)}: "
            f"<a href='tables/{html.escape(viewer.name)}' target='_blank' rel='noopener'>open table view</a> · "
            f"<a href='tables/{html.escape(csv_name)}' target='_blank' rel='noopener'>raw csv</a></li>"
        )
    beam_links_html = f"<ul>{''.join(beam_links)}</ul>" if beam_links else ""

    # ── Cube link ────────────────────────────────────────────────────────
    cube_path = data_root / "phase2" / "leakage_cube.nc"
    if cube_path.exists():
        cube_size_kb = cube_path.stat().st_size / 1024
        cube_link_html = (
            f"<p><a href='../phase2/leakage_cube.nc' download>leakage_cube.nc</a>"
            f" ({cube_size_kb:.0f}&nbsp;KB)</p>"
        )
    else:
        cube_link_html = "<p class='meta'>Cube file not found &mdash; run <code>build_leakage_cube.py</code> first.</p>"

    # ── Build index page ────────────────────────────────────────────────
    html_content = f"""<!doctype html>
<html lang='en'>
<head>
  <meta charset='utf-8' />
  <meta name='viewport' content='width=device-width, initial-scale=1' />
  <title>Summary of Residual On-axis Leakage</title>
  <style>
    body {{ font-family: Arial, sans-serif; margin: 24px; line-height: 1.4; }}
    h1, h2, h3 {{ margin: 0.6em 0 0.3em; }}
    ul {{ margin-top: 0.2em; }}
    table {{ border-collapse: collapse; width: 100%; margin: 12px 0 24px; font-size: 13px; }}
    th, td {{ border: 1px solid #ccc; padding: 6px 8px; text-align: left; }}
    th {{ background: #f3f3f3; position: sticky; top: 0; }}
    .meta {{ color: #444; font-size: 13px; }}
    a {{ color: #0366d6; }}
  </style>
  <script>
      window.MathJax = {{
          tex: {{ inlineMath: [['\\\\(','\\\\)']] }},
          svg: {{ fontCache: 'global' }}
      }};
  </script>
  <script defer src="https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-svg.js"></script>
</head>
<body>
  <h1>Summary of Residual On-axis Leakage</h1>
  <p class='meta'>Scope: MVP subset (indices 14&ndash;35, excluding 24&ndash;29).</p>

  <h2>Column legend</h2>
  <p class='meta'><b>Notation convention:</b> the superscript in parentheses denotes the index (dimension) over which the statistic is computed.
     For example, \\(\\mu^{{(s)}}\\) = median over SB_REF observations \\(s\\); \\(\\mu^{{(b)}}\\) = median over beams \\(b\\).
     Subscripts denote the free indices the result depends on.</p>
  <table>
    <thead><tr><th>Column</th><th>Meaning</th></tr></thead>
    <tbody>
      <tr><td>ODC weight</td><td>ODC WEIGHTS ID</td></tr>
      <tr><td>Variant</td><td>Bandpass calibrated (regular) or Bandpass + Leakage on-axis calibrated (lcal)</td></tr>
      <tr><td>Reference field</td><td>Name (with skyPos) of the field used for calibration</td></tr>
      <tr><td>n_obs(f)</td><td>Number of independent observations for this field (per ODC weight)</td></tr>
      <tr><td>Observed SB_REF IDs</td><td>Clickable links to diagnostic plots for these SB_REFs</td></tr>
      <tr><td>&mu;&#8317;&#7495;&#8318;</td><td>Median across beams of \\(\\mu_{{b,f}}^{{(s)}}\\)</td></tr>
      <tr><td>MAD&#8317;&#7495;&#8318;</td><td>MAD across beams of \\(\\mu_{{b,f}}^{{(s)}}\\) &mdash; beam-to-beam spread</td></tr>
      <tr><td>min&#8317;&#7495;&#8318;</td><td>Minimum across beams of \\(\\mu_{{b,f}}^{{(s)}}\\)</td></tr>
      <tr><td>max&#8317;&#7495;&#8318;</td><td>Maximum across beams of \\(\\mu_{{b,f}}^{{(s)}}\\)</td></tr>
    </tbody>
  </table>
  <p class='meta'>All statistics are over percentage linear polarisation leakage, \\(dL\\) (%).
     \\(dL = 100 \\times L/I\\), where \\(L\\) is the linear polarisation intensity and \\(I\\) is the Stokes&nbsp;I total intensity.</p>

  <h2>Bandpass calibrated</h2>
  {build_summary_table(field_regular, plots_dir=output_dir / 'plots')}

  <h2>Bandpass + Leakage (on-axis) calibrated</h2>
  {build_summary_table(field_lcal, plots_dir=output_dir / 'plots')}

  <h2>Footprint heatmaps</h2>
  <p class='meta'>Beam-layout footprint plots of residual leakage (dL&nbsp;%) for each reference field, faceted by ODC weight and calibration variant.</p>
  {footprint_links_html}

  <h2>3D Leakage cube (NetCDF4)</h2>
  <p class='meta'>The leakage data is stored as a labelled 3-D <a href='https://www.unidata.ucar.edu/software/netcdf/' target='_blank'>NetCDF4</a> cube
     with dimensions <b>beam</b>&nbsp;(36) &times; <b>field</b>&nbsp;(N) &times; <b>odc</b>&nbsp;(M).<br>
     Variables: <code>dL_regular</code>, <code>dL_lcal</code>, <code>p90_regular</code>, <code>p90_lcal</code>, <code>nsb_regular</code>, <code>nsb_lcal</code>.<br>
     Open with <code>xarray.open_dataset('leakage_cube.nc')</code> for programmatic slicing, outlier detection, or further analysis.</p>
  {cube_link_html}

  <h3>Supporting CSV tables</h3>
  <p class='meta'>Pre-averaged (beam &times; candidate) tables used to build the cube.</p>
  {beam_links_html}

  <h3>Run summary</h3>
  <ul><li>phase2_mvp_summary.md:
    <a href='tables/phase2_mvp_summary.md' target='_blank' rel='noopener'>open</a></li></ul>
</body>
</html>
"""

    index_path = output_dir / "index.html"
    index_path.write_text(html_content)

    print(f"Wrote {index_path}")
    print(f"Wrote copied artifacts under {tables_dir}")


if __name__ == "__main__":
    main()
