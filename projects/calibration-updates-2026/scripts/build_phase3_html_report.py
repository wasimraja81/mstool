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


# ---------------------------------------------------------------------------
# Manifest parsing
# ---------------------------------------------------------------------------

def parse_manifest(path: Path) -> list:
    """Parse sb_manifest_reffield_average.txt into a list of row dicts.

    Each dict has keys: idx, sb_ref, sb_1934, sb_holo, sb_target,
    odc_weight, ref_fieldname.
    """
    rows = []
    with path.open() as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            tokens = line.split()
            if len(tokens) < 5:
                continue
            try:
                row = {
                    "idx":       int(tokens[0]),
                    "sb_ref":    tokens[1],
                    "sb_1934":   tokens[2],
                    "sb_holo":   tokens[3],
                    "sb_target": tokens[4],
                    "odc_weight":    "",
                    "ref_fieldname": "",
                }
            except (ValueError, IndexError):
                continue
            for tok in tokens[5:]:
                if "=" in tok:
                    k, v = tok.split("=", 1)
                    if k == "ODC_WEIGHT":
                        row["odc_weight"] = v
                    elif k == "REF_FIELDNAME":
                        row["ref_fieldname"] = v
            rows.append(row)
    return rows


# ---------------------------------------------------------------------------
# Media file helpers
# ---------------------------------------------------------------------------

#: (filename_template, kind, variant_tag)
#: variant_tag: "" = regular, ".lcal" = lcal
_MEDIA_FILE_SPECS = [
    ("{stem}.combined_beams.pdf",        "pdf",         ""),
    ("{stem}.combined_beams.lcal.pdf",   "pdf",         ".lcal"),
    ("{stem}.beams_stokes.mp4",          "mp4_stokes",  ""),
    ("{stem}.beams_stokes.lcal.mp4",     "mp4_stokes",  ".lcal"),
    ("{stem}.beams_pol-degree.mp4",      "mp4_poldeg",  ""),
    ("{stem}.beams_pol-degree.lcal.mp4", "mp4_poldeg",  ".lcal"),
    ("{stem}.beams_stokes.gif",          "gif_stokes",  ""),
    ("{stem}.beams_stokes.lcal.gif",     "gif_stokes",  ".lcal"),
    ("{stem}.beams_pol-degree.gif",      "gif_poldeg",  ""),
    ("{stem}.beams_pol-degree.lcal.gif", "gif_poldeg",  ".lcal"),
    ("{stem}.leakage_stats.png",         "png_lstats",  ""),
    ("{stem}.leakage_stats.lcal.png",    "png_lstats",  ".lcal"),
]


def _media_stem(sb_ref, sb_1934, sb_holo, sb_target):
    return (
        f"SB_REF-{sb_ref}_SB_1934-{sb_1934}_SB_HOLO-{sb_holo}_SB_TARGET_1934-{sb_target}_"
        f"scienceData.Bandpass_closepack36_920MHz_0.9_1MHz.SB{sb_target}"
    )


def copy_media_files(manifest_rows: list, data_root: Path, media_dir: Path) -> dict:
    """Copy assessment media files into phase3/media/SB_REF-{r}/.

    Returns dict: sb_ref -> {'stem': str, 'present': set_of_filenames}
    """
    amp_suffix = "AMP_STRATEGY-multiply-insituPreflags"
    result = {}
    for row in manifest_rows:
        sb_ref    = row["sb_ref"]
        sb_1934   = row["sb_1934"]
        sb_holo   = row["sb_holo"]
        sb_target = row["sb_target"]
        stem = _media_stem(sb_ref, sb_1934, sb_holo, sb_target)
        src_dir = (
            data_root
            / f"SB_REF-{sb_ref}_SB_1934-{sb_1934}_SB_HOLO-{sb_holo}_{amp_suffix}"
            / f"1934-processing-SB-{sb_target}"
            / "assessment_results"
        )
        if not src_dir.is_dir():
            result[sb_ref] = {"stem": stem, "present": set()}
            continue
        dst_dir = media_dir / f"SB_REF-{sb_ref}"
        dst_dir.mkdir(parents=True, exist_ok=True)
        present = set()
        for tmpl, _kind, _vtag in _MEDIA_FILE_SPECS:
            fname = tmpl.replace("{stem}", stem)
            src = src_dir / fname
            dst = dst_dir / fname
            if src.exists():
                if not dst.exists():
                    shutil.copy2(src, dst)
                present.add(fname)
        # Also pick up pre-generated PNG pages (from convert_pdfs_to_png.py).
        # These may live in src_dir (if converted there) or already in dst_dir
        # (if convert_pdfs_to_png.py was run directly on phase3/media/).
        for png in sorted(src_dir.glob(f"{stem}.combined_beams*_p0*.png")):
            dst = dst_dir / png.name
            if not dst.exists():
                shutil.copy2(png, dst)
            present.add(png.name)
        for png in sorted(dst_dir.glob(f"{stem}.combined_beams*_p0*.png")):
            present.add(png.name)
        result[sb_ref] = {"stem": stem, "present": present}
    return result


def convert_pdfs_to_pngs(media_info: dict, media_dir: Path, dpi: int = 150) -> None:
    """Rasterise combined_beams PDFs to 2 PNG files (one per page) via Ghostscript.

    Skips pages that already exist on disk.  Updates media_info in-place with
    the newly created PNG filenames so downstream builders can use them.
    """
    import shutil as _shutil
    import subprocess
    gs_bin = _shutil.which("gs")
    if gs_bin is None:
        print("WARNING: gs (Ghostscript) not found – skipping PDF→PNG conversion.")
        return
    for sb_ref, info in media_info.items():
        stem    = info["stem"]
        present = info["present"]
        dst_dir = media_dir / f"SB_REF-{sb_ref}"
        if not dst_dir.is_dir():
            continue
        for vtag in ("", ".lcal"):
            pdf_fname = f"{stem}.combined_beams{vtag}.pdf"
            if pdf_fname not in present:
                continue
            pdf_path = dst_dir / pdf_fname
            if not pdf_path.exists():
                continue
            for page_num, page_label in [(1, "p01"), (2, "p02")]:
                png_fname = f"{stem}.combined_beams{vtag}_{page_label}.png"
                png_path  = dst_dir / png_fname
                if png_path.exists():
                    present.add(png_fname)  # already done
                    continue
                print(f"  [{sb_ref}] PDF→PNG page {page_num} [{vtag or 'regular'}] … ", end="", flush=True)
                subprocess.run(
                    [
                        gs_bin, "-q", "-dBATCH", "-dNOPAUSE", "-dSAFER",
                        "-sDEVICE=png16m",
                        f"-r{dpi}",
                        f"-dFirstPage={page_num}",
                        f"-dLastPage={page_num}",
                        f"-sOutputFile={png_path}",
                        str(pdf_path),
                    ],
                    check=True,
                )
                print(f"{png_path.stat().st_size // 1024} KB")
                present.add(png_fname)


# ---------------------------------------------------------------------------
# Leakage spectra section builder
# ---------------------------------------------------------------------------

def build_spectra_cards(manifest_rows: list, media_info: dict,
                        media_rel_prefix: str = "media") -> str:
    """Return HTML for the 'Leakage spectra' section.

    One <details id='sbref-{r}'> card per SB_REF, sorted by ODC then field.
    Each card has a 2×2 video grid (stokes/pol-degree × regular/lcal)
    plus inline PDFs for combined_beams.
    """
    # Sort by (odc_weight, ref_fieldname, sb_ref); skip rows with no media on disk
    ordered = sorted(
        [
            r for r in manifest_rows
            if r["sb_ref"] in media_info and media_info[r["sb_ref"]]["present"]
        ],
        key=lambda r: (r["odc_weight"], r["ref_fieldname"], r["sb_ref"]),
    )
    cards = []
    for row in ordered:
        sb_ref = row["sb_ref"]
        info   = media_info[sb_ref]
        stem   = info["stem"]
        present = info["present"]
        odc    = row["odc_weight"]
        field  = row["ref_fieldname"]
        card_id = f"sbref-{sb_ref}"
        rel    = f"{media_rel_prefix}/SB_REF-{sb_ref}"

        # ── 2×2 video grid ────────────────────────────────────────────
        grid_cells = []
        for variant_label, vtag in [("regular", ""), ("lcal", ".lcal")]:
            for plot_stem, plot_label in [
                ("beams_stokes",    "Stokes"),
                ("beams_pol-degree","Pol. degree"),
            ]:
                mp4_fname = f"{stem}.{plot_stem}{vtag}.mp4"
                gif_fname = f"{stem}.{plot_stem}{vtag}.gif"
                mp4_href  = f"{rel}/{quote(mp4_fname)}"
                gif_href  = f"{rel}/{quote(gif_fname)}"
                inner = (
                    f"<p style='margin:0 0 6px'><b>{html.escape(plot_label)}"
                    f" <span style='font-weight:normal;color:#666'>[{html.escape(variant_label)}]</span></b></p>"
                )
                btns = []
                if mp4_fname in present:
                    btns.append(
                        f"<button class='media-btn' "
                        f"onclick=\"openModal('{mp4_href}','video')\">"
                        f"&#9654; MP4</button>"
                    )
                if gif_fname in present:
                    btns.append(
                        f"<button class='media-btn media-btn--gif' "
                        f"onclick=\"openModal('{gif_href}','gif')\">"
                        f"&#128247; GIF</button>"
                    )
                # All-beams combined PNG (p01 = Stokes, p02 = Pol. degree)
                page_tag = "p01" if plot_stem == "beams_stokes" else "p02"
                png_all  = f"{stem}.combined_beams{vtag}_{page_tag}.png"
                if png_all in present:
                    png_href_all = f"{rel}/{quote(png_all)}"
                    btns.append(
                        f"<button class='media-btn'"
                        f" onclick=\"openModal('{png_href_all}','img')\">"
                        f"&#8862; all beams</button>"
                    )
                # Leakage stats (beamwise, channel-averaged) — only for pol-degree cells
                if plot_stem == "beams_pol-degree":
                    lstats_fname = f"{stem}.leakage_stats{vtag}.png"
                    if lstats_fname in present:
                        lstats_href = f"{rel}/{quote(lstats_fname)}"
                        btns.append(
                            f"<button class='media-btn media-btn--beamwise'"
                            f" onclick=\"openModal('{lstats_href}','img')\">"
                            f"&#128200; beamwise</button>"
                        )
                if btns:
                    inner += f"<p style='margin:4px 0 0'>{' '.join(btns)}</p>"
                else:
                    inner += "<span style='color:#888;font-size:12px'>(not available)</span>"
                grid_cells.append(
                    f"<td style='padding:10px;vertical-align:top;width:25%'>{inner}</td>"
                )
        grid_html = (
            "<table style='width:100%;border-collapse:collapse;border:none'>"
            f"<tr>{''.join(grid_cells)}</tr>"
            "</table>"
        )

        summary_text = (
            f"SB_REF-{html.escape(sb_ref)}"
            f"&nbsp;&nbsp;&middot;&nbsp;&nbsp;ODC-{html.escape(odc)}"
            f"&nbsp;&nbsp;&middot;&nbsp;&nbsp;{html.escape(field)}"
        )
        cards.append(
            f"<details id='{card_id}'"
            f" style='margin:6px 0;border:1px solid #ddd;border-radius:4px'>"
            f"<summary style='cursor:pointer;padding:8px 12px;font-weight:bold'>"
            f"{summary_text}</summary>"
            f"<div style='padding:10px 14px'>"
            f"{grid_html}"
            f"</div>"
            f"</details>"
        )

    if not cards:
        return "<p class='meta'>No media files found – run <code>copy_media_files()</code> first.</p>"
    return "\n".join(cards)


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


def build_summary_table(rows, plots_dir=None, media_map=None):
    """Render an inline HTML table with summary columns and clickable SB_REF links.

    If plots_dir is given, the reference-field cell links to the individual
    footprint PNG for that (field, ODC, variant) combination.

    If media_map is given ({sb_ref: {'stem': str, 'present': set}}), the
    sb_ref_values column gains anchor + download links (↓pdf, ↓mp4, ↓gif).
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
                field_safe = str(v).replace("/", "_")
                odc = row.get("odc_weight", "")
                vtag = str(row.get("variant", ""))  # "regular" or "lcal"
                # Badge 1: per-(odc, variant) dL footprint
                dl_png = f"footprint_dL_{field_safe}_odc{odc}_{vtag}.png"
                if (plots_dir / dl_png).exists():
                    dl_badge = (
                        f" <a href='plots/{quote(dl_png)}'"
                        f" onclick=\"openModal(this.href,'img');return false;\""
                        f" class='plot-badge'>L</a>"
                    )
                else:
                    dl_badge = ""
                # Badge 2: per-(odc, variant) Q/U footprint
                qu_png = f"footprint_QU_{field_safe}_odc{odc}_{vtag}.png"
                if (plots_dir / qu_png).exists():
                    qu_badge = (
                        f" <a href='plots/{quote(qu_png)}'"
                        f" onclick=\"openModal(this.href,'img');return false;\""
                        f" class='plot-badge'>|Q|,|U|</a>"
                    )
                else:
                    qu_badge = ""
                cells.append(f"<td>{html.escape(str(v))}{dl_badge}{qu_badge}</td>")
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
                badge_parts = []
                for sb in parts:
                    anchor = f"#sbref-{sb}"
                    badge_parts.append(
                        f"<a href='{html.escape(anchor)}'"
                        f" onclick=\"openSpectraCard('sbref-{html.escape(sb)}');return false;\">"
                        f"SB_REF-{html.escape(sb)}</a>"
                    )
                cells.append(f"<td>{'<br>'.join(badge_parts)}</td>")
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


def assemble_package(
    package_dir: Path,
    phase3_dir: Path,
    cube_src: Path,
    media_info: dict,
) -> None:
    """Assemble a self-contained shareable package.

    Copies:
      - plots/ — all PNGs (footprint_dL_*, footprint_QU_*, single-panel variants)
      - media/ — PNGs (combined_beams pages, leakage_stats) + MP4s only (no GIFs)
      - leakage_cube.nc
    Patches index.html: removes GIF buttons + CSS, fixes cube href, drops
    the Run summary section.
    """
    import re
    package_dir.mkdir(parents=True, exist_ok=True)
    (package_dir / "plots").mkdir(exist_ok=True)
    (package_dir / "media").mkdir(exist_ok=True)

    # ── plots/ ────────────────────────────────────────────────────────
    n_plots = 0
    for f in sorted((phase3_dir / "plots").glob("*.png")):
        shutil.copy2(f, package_dir / "plots" / f.name)
        n_plots += 1
    print(f"  plots: {n_plots} PNGs")

    # ── cube ──────────────────────────────────────────────────────────
    if cube_src.exists():
        shutil.copy2(cube_src, package_dir / "leakage_cube.nc")
        print(f"  cube:  {cube_src.stat().st_size // 1024} KB")
    else:
        print("  cube:  not found, skipping")

    # ── media: PNG + MP4 only ─────────────────────────────────────────
    n_png = n_mp4 = 0
    for sb_ref, info in media_info.items():
        present = info.get("present", set())
        if not present:
            continue
        src_dir = phase3_dir / "media" / f"SB_REF-{sb_ref}"
        dst_dir = package_dir / "media" / f"SB_REF-{sb_ref}"
        dst_dir.mkdir(parents=True, exist_ok=True)
        for fname in sorted(present):
            if not (fname.endswith(".png") or fname.endswith(".mp4")):
                continue
            src = src_dir / fname
            if src.exists():
                shutil.copy2(src, dst_dir / fname)
                if fname.endswith(".png"): n_png += 1
                else:                      n_mp4 += 1
    print(f"  media: {n_png} PNGs, {n_mp4} MP4s")

    # ── Patch index.html ──────────────────────────────────────────────
    src_html = (phase3_dir / "index.html").read_text()

    # 1. Strip GIF modal buttons
    patched = re.sub(
        r"<button class='media-btn media-btn--gif'[^>]*>.*?</button>",
        "",
        src_html,
        flags=re.DOTALL,
    )
    # 1b. Strip dead GIF CSS rules
    patched = re.sub(r"\s*\.media-btn--gif\b[^}]*\}", "", patched)
    # 2. Fix cube href: ../phase2/leakage_cube.nc  ->  leakage_cube.nc
    patched = patched.replace("'../phase2/leakage_cube.nc'", "'leakage_cube.nc'")

    # 3. Drop Supporting CSV tables + Run summary (everything between
    #    their first <h3> tag and the closing </ul> before the modal comment)
    patched = re.sub(
        r"\s*<h3>Supporting CSV tables</h3>.*?</ul>(?=\s*\n\s*<!--)",
        "",
        patched,
        flags=re.DOTALL,
    )

    (package_dir / "index.html").write_text(patched)

    total = sum(f.stat().st_size for f in package_dir.rglob("*") if f.is_file())
    print(f"Package ready at {package_dir}  ({total / 1e6:.1f} MB total)")


def run_upstream_pipeline(data_root: Path, phase2_dir: Path) -> None:
    """Run the three upstream pipeline scripts in order:
      1. build_phase2_isolation_tables.py  — (re)generate phase-2 CSVs
      2. build_leakage_cube.py             — rebuild leakage_cube.nc
      3. plot_leakage_footprint.py         — regenerate footprint PNGs (dL + QU)

    Only runs if the master leakage CSV exists.  Uses the same Python
    interpreter as the current process.  Failures are reported but do not
    abort the HTML build (existing outputs will still be used).
    """
    import subprocess
    import sys

    scripts_dir = Path(__file__).resolve().parent
    python = sys.executable

    master_csv  = data_root / "leakage_master_table.csv"

    if not master_csv.exists():
        print(f"Upstream pipeline skipped: master CSV not found at {master_csv}")
        return

    steps = [
        (
            "Phase-2 isolation tables",
            [python, str(scripts_dir / "build_phase2_isolation_tables.py"),
             "--input-csv", str(master_csv),
             "--output-dir", str(phase2_dir)],
        ),
        (
            "Leakage cube (NetCDF4)",
            [python, str(scripts_dir / "build_leakage_cube.py"),
             "--data-root", str(data_root)],
        ),
        (
            "Footprint plots (dL + QU)",
            [python, str(scripts_dir / "plot_leakage_footprint.py"),
             "--data-root", str(data_root)],
        ),
    ]

    for label, cmd in steps:
        print(f"\n── Running: {label} ──")
        result = subprocess.run(cmd, text=True)
        if result.returncode != 0:
            print(f"  WARNING: '{label}' exited with code {result.returncode} — continuing with existing outputs.")


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
    parser.add_argument(
        "--manifest",
        default=None,
        help=(
            "Path to sb_manifest_reffield_average.txt. "
            "If omitted, the script searches <repo>/projects/calibration-updates-2026/manifests/ "
            "then <data-root> for a file named sb_manifest_reffield_average.txt."
        ),
    )
    parser.add_argument(
        "--package",
        default=None,
        metavar="PATH",
        help=(
            "If given, assemble a self-contained shareable package at this path. "
            "Includes only PNG + MP4 + plots + cube; strips GIFs, PDFs and CSV tables."
        ),
    )
    args = parser.parse_args()

    data_root = Path(args.data_root)
    phase2_dir = Path(args.phase2_dir) if args.phase2_dir else data_root / "phase2"
    output_dir = Path(args.output_dir) if args.output_dir else data_root / "phase3"
    asset_root = Path(args.asset_root)
    asset_http_base = args.asset_http_base
    tables_dir = output_dir / "tables"
    media_dir  = output_dir / "media"

    output_dir.mkdir(parents=True, exist_ok=True)
    tables_dir.mkdir(parents=True, exist_ok=True)
    media_dir.mkdir(parents=True, exist_ok=True)

    # ── Locate manifest ──────────────────────────────────────────────────
    manifest_path = None
    if args.manifest:
        manifest_path = Path(args.manifest)
    else:
        # Search heuristic
        candidates = [
            Path(__file__).resolve().parent.parent / "manifests" / "sb_manifest_reffield_average.txt",
            data_root / "sb_manifest_reffield_average.txt",
        ]
        for c in candidates:
            if c.exists():
                manifest_path = c
                break

    manifest_rows: list = []
    media_info: dict    = {}
    if manifest_path and manifest_path.exists():
        manifest_rows = parse_manifest(manifest_path)
        print(f"Parsed {len(manifest_rows)} manifest rows from {manifest_path}")
        media_info = copy_media_files(manifest_rows, data_root, media_dir)
        convert_pdfs_to_pngs(media_info, media_dir)
        n_copied = sum(len(v["present"]) for v in media_info.values())
        print(f"Media ready for {len(media_info)} SB_REFs ({n_copied} files total under {media_dir})")
    else:
        print("Warning: no manifest found – Obs column and spectra cards will be empty.")

    # media_map for the summary table: {sb_ref: {'stem', 'present'}}
    media_map = media_info if media_info else None

    # ── Run upstream pipeline steps ──────────────────────────────────────
    run_upstream_pipeline(data_root, phase2_dir)

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
    combined_footprint_rows = []
    for fname in unique_fields:
        safe = fname.replace("/", "_")
        png_l  = f"footprint_dL_{safe}.png"
        png_qu = f"footprint_QU_{safe}.png"
        l_badge = (
            f"<a href='plots/{quote(png_l)}'"
            f" onclick=\"openModal(this.href,'img');return false;\""
            f" class='plot-badge'>L</a>"
            if (plots_dir / png_l).exists() else ""
        )
        qu_badge = (
            f"<a href='plots/{quote(png_qu)}'"
            f" onclick=\"openModal(this.href,'img');return false;\""
            f" class='plot-badge'>|Q|,|U|</a>"
            if (plots_dir / png_qu).exists() else ""
        )
        if l_badge or qu_badge:
            combined_footprint_rows.append(
                f"<tr><td class='field-name'>{html.escape(fname)}</td>"
                f"<td>{l_badge}</td><td>{qu_badge}</td></tr>"
            )
    if combined_footprint_rows:
        combined_footprint_html = (
            "<table class='footprint-overview'>"
            "<thead><tr><th>Field</th><th>L</th><th>|Q|,|U|</th></tr></thead>"
            "<tbody>" + "".join(combined_footprint_rows) + "</tbody></table>"
        )
    else:
        combined_footprint_html = "<p class='meta'>No footprint plots found.</p>"

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
# ── Leakage spectra cards (per SB_REF) ──────────────────────────────
    spectra_cards_html = build_spectra_cards(manifest_rows, media_info)

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
    .plot-badge {{ display:inline-block;font-size:10px;font-weight:bold;padding:1px 5px;border-radius:3px;border:1px solid #0366d6;color:#0366d6;text-decoration:none;margin-left:4px;white-space:nowrap; }}
    .plot-badge:hover {{ background:#0366d6;color:#fff; }}
    .footprint-overview {{ border-collapse:collapse;margin:8px 0; }}
    .footprint-overview th {{ font-size:11px;font-weight:600;padding:3px 12px 3px 6px;border-bottom:1px solid #ccc;text-align:left;color:#555; }}
    .footprint-overview td {{ padding:3px 8px 3px 6px;font-size:12px;vertical-align:middle; }}
    .footprint-overview td.field-name {{ font-family:monospace;font-size:12px;padding-right:14px; }}
    .footprint-overview tr:hover td {{ background:#f0f6ff; }}
    .media-btn {{ display:inline-flex;align-items:center;height:26px;background:#0366d6;color:#fff;border:none;padding:0 11px;border-radius:4px;cursor:pointer;font-size:12px;margin-right:6px;margin-bottom:4px;white-space:nowrap; }}
    .media-btn:hover {{ background:#0256b4; }}
    .media-btn--gif {{ background:#28a745; }}
    .media-btn--gif:hover {{ background:#1e7e34; }}
    .media-btn--beamwise {{ background:#28a745; }}
    .media-btn--beamwise:hover {{ background:#1e7e34; }}
    .media-btn--page {{ background:#6c757d; }}
    .media-btn--page:hover {{ background:#545b62; }}
    #media-modal {{ display:none;position:fixed;inset:0;background:rgba(0,0,0,0.82);z-index:9999;align-items:center;justify-content:center; }}
    #media-modal-box {{ position:relative;max-width:92vw;max-height:92vh;text-align:center; }}
    #media-modal-close {{ position:absolute;top:-36px;right:0;background:none;border:none;color:#fff;font-size:28px;line-height:1;cursor:pointer; }}
    #media-modal-content video {{ max-width:88vw;max-height:85vh;display:block;border-radius:4px; }}
    #media-modal-scroll {{ overflow:auto;max-width:90vw;max-height:86vh;border-radius:4px; }}
    #media-modal-scroll::-webkit-scrollbar {{ height:10px;width:10px; }}
    #media-modal-scroll::-webkit-scrollbar-thumb {{ background:#888;border-radius:5px; }}
    #media-modal-scroll::-webkit-scrollbar-track {{ background:#2a2a2a;border-radius:5px; }}
  </style>
  <script>
      window.MathJax = {{
          tex: {{ inlineMath: [['\\\\(','\\\\)']] }},
          svg: {{ fontCache: 'global' }}
      }};
  </script>
  <script defer src="https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-svg.js"></script>
  <script>
    function openSpectraCard(id) {{
      var el = document.getElementById(id);
      if (el) {{ el.open = true; el.scrollIntoView({{behavior: 'smooth', block: 'start'}}); }}
      return false;
    }}
    function toggleImgZoom(img) {{
      var hint = document.getElementById('media-modal-hint');
      if (img.dataset.zoomed === '1') {{
        img.style.maxWidth = '88vw'; img.style.maxHeight = '85vh'; img.style.width = '';
        img.style.cursor = 'zoom-in'; img.dataset.zoomed = '0';
        if (hint) hint.textContent = 'Click to zoom \u00b7 Esc / click outside to close';
      }} else {{
        img.style.maxWidth = 'none'; img.style.maxHeight = 'none'; img.style.width = 'auto';
        img.style.cursor = 'zoom-out'; img.dataset.zoomed = '1';
        if (hint) hint.textContent = 'Scroll \u2195\u2194 to pan \u00b7 Click to zoom out \u00b7 Esc / click outside to close';
      }}
    }}
    function openModal(url, type) {{
      var box = document.getElementById('media-modal-content');
      if (type === 'video') {{
        box.innerHTML = '<video src="' + url + '" autoplay loop muted playsinline controls></video>';
      }} else if (type === 'img') {{
        box.innerHTML = '<div id="media-modal-scroll">'
          + '<img src="' + url + '" alt="preview" data-zoomed="0"'
          + ' style="display:block;max-width:88vw;max-height:85vh;cursor:zoom-in"'
          + ' onclick="toggleImgZoom(this)"></div>'
          + '<p id="media-modal-hint" style="color:#ccc;font-size:12px;margin:6px 0 0">Click to zoom \u00b7 Esc / click outside to close</p>';
      }} else {{
        box.innerHTML = '<img src="' + url + '" alt="preview">';
      }}
      var modal = document.getElementById('media-modal');
      modal.style.display = 'flex';
      document.body.style.overflow = 'hidden';
    }}
    function closeModal() {{
      document.getElementById('media-modal').style.display = 'none';
      document.getElementById('media-modal-content').innerHTML = '';
      document.body.style.overflow = '';
    }}
    document.addEventListener('keydown', function(e) {{ if (e.key === 'Escape') closeModal(); }});
  </script>
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
      <tr><td>Observed SB_REF IDs</td><td>Links to the leakage statistics card for each individual SB_REF observation</td></tr>
      <tr><td>&mu;&#8317;&#7495;&#8318;</td><td>Median across beams of \\(\\mu_{{b,f}}^{{(s)}}\\)</td></tr>
      <tr><td>MAD&#8317;&#7495;&#8318;</td><td>MAD across beams of \\(\\mu_{{b,f}}^{{(s)}}\\) &mdash; beam-to-beam spread</td></tr>
      <tr><td>min&#8317;&#7495;&#8318;</td><td>Minimum across beams of \\(\\mu_{{b,f}}^{{(s)}}\\)</td></tr>
      <tr><td>max&#8317;&#7495;&#8318;</td><td>Maximum across beams of \\(\\mu_{{b,f}}^{{(s)}}\\)</td></tr>
    </tbody>
  </table>
  <p class='meta'>All statistics are over percentage linear polarisation leakage, \\(dL\\) (%).
     \\(dL = 100 \\times L/I\\), where \\(L\\) is the linear polarisation intensity and \\(I\\) is the Stokes&nbsp;I total intensity.</p>

  <h2>Bandpass calibrated</h2>
  {build_summary_table(field_regular, plots_dir=output_dir / 'plots', media_map=media_map)}

  <h2>Bandpass + Leakage (on-axis) calibrated</h2>
  {build_summary_table(field_lcal, plots_dir=output_dir / 'plots', media_map=media_map)}

  <h2>Footprint heatmaps</h2>
  <p class='meta'>Beam-layout footprint plots for each reference field. <b>L</b>: residual leakage dL&nbsp;=&nbsp;&radic;(Q&sup2;+U&sup2;)/I (%), faceted by ODC weight and calibration variant. <b>|Q|,|U|</b>: split-circle plots of |Q|/I (top-left) and |U|/I (bottom-right).</p>
  {combined_footprint_html}

  <h2>Leakage statistics for beams (per SB_REF)</h2>
  <p class='meta'>Per-observation plots, one card per SB_REF. Each card is collapsed by default — click a row to expand.
    Within each card: <b>Stokes</b> and <b>pol. degree</b> animations (MP4/GIF) plus <b>&#8862;&nbsp;all beams</b> grid images for both calibration variants (regular / lcal).
    The pol. degree cells also include a <b>&#128200;&nbsp;beamwise</b> button opening the channel-averaged leakage statistics plot (x-axis = BeamNum).</p>
  {spectra_cards_html}

  <h2>3D Leakage cube (NetCDF4)</h2>
  <p class='meta'>The leakage data is stored as a labelled 3-D <a href='https://www.unidata.ucar.edu/software/netcdf/' target='_blank'>NetCDF4</a> cube
     with dimensions <b>beam</b>&nbsp;(36) &times; <b>field</b>&nbsp;(N) &times; <b>odc</b>&nbsp;(M).<br>
     Variables: <code>dL_regular</code>, <code>dL_lcal</code>, <code>p90_regular</code>, <code>p90_lcal</code>, <code>nsb_regular</code>, <code>nsb_lcal</code>.<br>
     Open with <code>xarray.open_dataset('leakage_cube.nc')</code> for programmatic slicing, outlier detection, or further analysis.</p>
  {cube_link_html}

  <h3>Run summary</h3>
  <ul><li>phase2_mvp_summary.md:
    <a href='tables/phase2_mvp_summary.md' target='_blank' rel='noopener'>open</a></li></ul>

  <!-- ── Media modal ─────────────────────────────────────────── -->
  <div id='media-modal' onclick="if(event.target===this)closeModal()">
    <div id='media-modal-box'>
      <button id='media-modal-close' onclick='closeModal()' title='Close (Esc)'>&#10005;</button>
      <div id='media-modal-content'></div>
    </div>
  </div>
</body>
</html>
"""

    index_path = output_dir / "index.html"
    index_path.write_text(html_content)

    print(f"Wrote {index_path}")
    print(f"Wrote copied artifacts under {tables_dir}")

    if args.package:
        print("\nAssembling shareable package …")
        assemble_package(
            package_dir=Path(args.package),
            phase3_dir=output_dir,
            cube_src=data_root / "phase2" / "leakage_cube.nc",
            media_info=media_info,
        )


if __name__ == "__main__":
    main()
