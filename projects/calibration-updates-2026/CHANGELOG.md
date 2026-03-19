# Changelog — calibration-u
## 3.9 — 2026-03-16

### PAF plots: transform fix, astronomical sky-view, shared helpers, metadata-driven annotations

- **Bug fix — `sky_to_paf_grid()` in `paf_port_layout.py`**: corrected sign
  constant from `−45°` to `+45°` in `na = radians(+45 − pol_axis_deg)`.
  The previous sign omitted the rear-view left-right mirror reflection;
  beam positions were systematically ~90° off. Verified against system
  scientist's beam→max-port table (0-based indexing confirmed; inner-beam
  agreement ≥ 17/36 exact after offset correction, consistent with
  Airy-theory vs max-SNR centroid difference for outer beams).

- **Duplicate-transform elimination**: `sky_to_paf()` in
  `plot_paf_beam_overlay.py` is now a thin wrapper delegating to the
  canonical `sky_to_paf_grid()` in `paf_port_layout.py`. Independent
  copies of the transform formula removed from both overlay and movie
  scripts; a single definition is the source of truth.

- **Astronomical sky-view convention (E left)**: all plots now display the
  standard astronomy orientation — sky-North up, sky-East **left**:
  - `grid_to_xy()` updated: `x = col − 6.5, y = row − 6.5` (col 1 at left,
    col 12 at right — East to the left).
  - `_leg_colour()` decoupled from `grid_to_xy()` — retains fixed rear-view
    formula so leg colours remain physically correct.
  - `sky_to_paf_grid()` returns `(u, −v)` (flip v-axis only for E-left).
  - East unit vector: `ed = [−nd[1], nd[0]]` (90° CCW from North) in all
    three scripts.
  - Leg/wedge labels, axis labels, and `frame_axis()` corner annotation
    updated to reflect the new orientation.
  - Arm-tip unpaired dots corrected for E-left direction.

- **Compass rose improvements** (`draw_compass_rose()` in `paf_port_layout.py`):
  - Single canonical implementation; both overlay and movie call it — no
    duplicate compass code.
  - Size reduced ~30% (`alen 1.10 → 0.77`, `wid 0.16 → 0.11`, font 8.5 → 6pt).
  - Repositioned to `0.87 × lim` (was `0.78 × lim`) to avoid overlapping Leg 4.
  - `pol_axis` label removed from under the compass pivot.

- **Parameter annotation box** — upper-right inset on both plots:
  - Shows: SB number + alias, frequency, pol_axis (+ source), footprint pitch,
    element pitch, beam count.
  - Movie title animates per-frame as `"<footprint> footprint … — beam N"`;
    `title_artist.set_animated(True)` for blit compatibility.

- **`draw_info_box()` added to `paf_port_layout.py`** — single canonical
  function for the annotation box; both overlay and movie import and call it,
  eliminating duplicated `ax.annotate()` blocks.

- **Footprint name read from metadata** — hardcoded `"closepack36"` removed
  from both script titles. Name is now resolved at runtime from the schedblock:
  1. `weights.footprint_name` (primary key)
  2. `common.target.src%d.footprint.name` (fallback)
  Scripts are now footprint-agnostic; the only hardcoded values are the MkII
  PAF physical layout constants in `paf_port_layout.py`.

- **All plotted parameters are metadata-driven**:
  | Parameter | Source |
  |---|---|
  | footprint name | schedblock (`weights.footprint_name`) |
  | pol_axis | schedblock (`common.target.src*.pol_axis`) |
  | frequency | schedblock (`weights.centre_frequency`) |
  | sbid / alias | schedblock header |
  | footprint pitch | derived from actual beam positions (min separation) |
  | element pitch | CLI `--elem-pitch` (default 0.677°, MkII physical constant) |
  | beam count | `len(beams)` from footprint file |

- **`run_paf_beam_overlay.sh`** — convenience caller for the overlay script,
  matching the style of `run_paf_beam_movie.sh`.

---

## 3.8 — 2026-03-15

### PAF beam-scan animation (new scripts)

- **`plot_paf_beam_movie.py`** — Generates an Airy-disk beam-scan animation (MP4)
  for a single SB_REF:
  - One frame per beam in footprint order; Airy pattern rendered on a fine grid
    using `scipy.special.j1` to the configurable N-th null (default: 3rd).
  - Optional trail accumulation: previous beams persist at a scaled alpha,
    giving a ghost-trail effect controlled by `--trail` (0 = no trail).
  - Display gamma power-law (`--gamma`) for ring contrast enhancement.
  - Configurable colourmap (`--cmap`, default `gray`), fps, DPI, hold frames,
    and grid resolution.
  - Port numbers shown on PAF elements; beam-number annotation suppressed.
  - Frame title shows SB_REF, field alias, frequency, and pol_axis.
  - Encoded to MP4 via `ffmpeg` (H.264, yuv420p, default output to
    `phase3/plots/paf_beam_movie_<SB_REF>.mp4`).
  - Key CLI flags: `--footprint`, `--schedblock`, `--output`, `--fps`,
    `--n-nulls`, `--trail`, `--gamma`, `--cmap`, `--dpi`, `--hold`,
    `--grid-res`.

- **`create_paf_beam_movie.sh`** — Manifest-driven shell wrapper:
  - Accepts `--manifest`, `--start-index`, `--end-index`, `--exclude-indices`
    (same conventions as `copy_and_combine_assessment_results.sh`).
  - Per-row path construction: reads `AMP_STRATEGY` and `DO_PREFLAG_REFTABLE`
    from each manifest row (with global manifest defaults), builds the
    `_AMP_STRATEGY-<amp>[-insituPreflags]` suffix via `build_strategy_suffix()`
    — handles any independent combination of amp strategy and preflag flag.
  - Resolves `footprintOutput-sb<REF>-<FIELD>.txt` (with `src1` fallback) and
    `schedblock-info-<REF>.txt` (with 1934 fallback) from `metadata/`.
  - Skips rows with excluded indices, missing `REF_FIELDNAME`, or absent
    metadata; summarises ok / skipped / missing_meta / failed counts.
  - `--force` flag to regenerate existing MP4s.

- **`run_paf_beam_movie.sh`** — Simple convenience caller:
  - Hardcodes the canonical manifest path and index range (14–42, excluding
    24–29); edit and run directly from the repo root.
  - Two commented-out variants: single-SB quick test, Blues+slow playback.

### Dependencies

- `scipy` added to `.venv` (required by `plot_paf_beam_movie.py` for `j1`).

---

## 3.7 — 2026-03-15

### PAF beam-overlay visualisation tools (new scripts)

- **`paf_port_layout.py`** — library + standalone plotter for the ASKAP MkII
  Phased Array Feed layout:
  - Canonical 112-element symmetric 12×12 grid; 94 x-ports + 94 y-ports
    = 188 total ports, numbered following the Reynolds convention.
  - Per-element leg colouring (Red/Green/Blue/Yellow quadrant split
    matching MkII wiring diagrams).
  - `sky_to_paf_grid()` — physically-motivated compass transform:
    `pol_axis=0` → Leg 4 toward North (Reynolds); East = 90° CW from North
    in rear-view; telescope focal-plane inversion applied.
  - `overlay_beam_footprint()` — parses footprintOutput files and overlays
    FWHM-sized beam circles (radius = `beam_fwhm_deg/2 / elem_pitch_deg`).
  - `_draw_sky_overlay()` — diagnostic stars (pointing, S-sky, W-sky) +
    N/E compass rose.
  - `plot_paf_polaxis_panels()` — 2×2 panel comparison for
    `pol_axis ∈ {0°, 45°, 60°, −45°}`.
  - `plot_paf_polaxis_footprint_panels()` — same 2×2 with beam footprints.
  - `plot_paf_layout()` — single full-panel layout with port-number labels.
  - Exports `build_port_table` and `draw_paf_elements` for use by other
    scripts.

- **`plot_paf_beam_overlay.py`** — CLI tool for overlaying a closepack-36
  beam footprint on the MkII PAF element grid:
  - Auto-reads `pol_axis`, centre frequency, SBID, and beam pitch from the
    schedblock metadata file; all can be overridden via CLI flags.
  - Beam circle radius computed from first-principles:
    `r = (1.02 λ/D / 2) / elem_pitch_deg` using `weights.centre_frequency`
    from the schedblock (e.g. 920.5 MHz → FWHM = 1.59°, r = 1.17 elem).
  - Compass rose with diamond needles always shown: N = red, E = steel-blue,
    S/W = white outline; `pol_axis` labelled underneath.
  - `--sky-markers` flag (off by default) enables diagnostic pointing star
    (red ★), South-sky star (gold ★) and West-sky star (cyan ★).
  - `--no-labels` suppresses beam-number annotations.
  - Title line includes SBID, field alias, pol_axis value and its source
    (schedblock / CLI / default).
  - Key CLI flags: `--footprint`, `--schedblock`, `--pol-axis`, `--freq-mhz`,
    `--dish-diam`, `--elem-pitch`, `--beam-radius`, `--sky-markers`,
    `--output`.

### Fixed

- **`build_phase3_html_report.py`** — semi-transparent cmap-sampled colours
  for Q/U footprint legend wedges (was fully opaque, obscured background).

---

## 3.6 — 2026-03-13

### Pipeline: Q/U leakage diagnostics

- **`build_phase2_isolation_tables.py`** — extended to propagate per-SB
  `leak_q_over_i_pct` and `leak_u_over_i_pct` columns through both the
  beam×field and beam×ODC isolation tables. Adds `median_q_over_i`,
  `p90_q_over_i`, `median_u_over_i`, `p90_u_over_i` to beam×field rows and
  the corresponding beam-level aggregates to the field-scores table.

- **`build_leakage_cube.py`** — adds four new cube variables:
  `dQ_bpcal`, `dQ_lcal`, `dU_bpcal`, `dU_lcal`
  (|Q|/I × 100 % and |U|/I × 100 %, median over valid channels).
  Gracefully skips empty variables with a status message.

- **`plot_leakage_footprint.py`** — adds split-circle Q/U footprint plots:
  - `plot_single_panel_qu()` — one PNG per (field, ODC, variant):
    `footprint_QU_{field}_odc{odc}_{vtag}.png`.
  - `plot_field_qu()` — all-ODC overview PNG per field:
    `footprint_QU_{field}.png`.
  - 45° diagonal split: Q top-left half, U bottom-right half.
  - Real `Wedge`-patch legend in each plot (no text-symbol approximation);
    size and font separately tuned for single-panel vs combined heatmaps.

### HTML report (`build_phase3_html_report.py`)

- **Footprint heatmaps section redesigned**: single compact table replaces
  the old two-block layout (separate L list + QU subheader). Each row:
  field name │ **L** badge → `footprint_dL_{field}.png` │
  **|Q|,|U|** badge → `footprint_QU_{field}.png`.
  L description now shows formula: dL = √(Q²+U²)/I.

- **Per-(ODC, variant) Q/U badge** added to every field-row in the summary
  table (links to `footprint_QU_{field}_odc{odc}_{vtag}.png`).

- **`leakage_stats` plots** (channel-averaged, x-axis = BeamNum) integrated
  into each SB_REF card within the Pol. degree column as a
  **📈 beamwise** button.

- **Section and button labels**:
  - "Leakage spectra (per SB_REF)" → "Leakage statistics for beams (per SB_REF)".
  - "Stokes spectra" → "Stokes".
  - "6×6 grid" (camera icon) → "⊞ all beams" (grid icon).

- **Uniform button height**: all media buttons use
  `display:inline-flex; align-items:center; height:26px` — consistent
  height regardless of icon or text content.

- **Blue/green/blue/green colour scheme**: MP4=blue, GIF=green,
  all-beams=blue, beamwise=green — consistent across all card cells.

- **`assemble_package()` + `--package <path>` CLI flag** — builds a
  self-contained shareable directory containing plots PNGs, media PNGs +
  MP4s, `leakage_cube.nc`, and a patched `index.html` with GIF buttons and
  CSV/run-summary sections stripped.

---

## 3.5 — 2026-03-13

### New scripts

- **`build_leakage_cube.py`** — Constructs a labelled 3-D NetCDF4 cube
  (`leakage_cube.nc`) from the Phase-2 beam×field CSV.
  Dimensions: beam (36) × field (N) × odc (M).
  Variables: `dL_bpcal`, `dL_lcal`, `p90_bpcal`, `p90_lcal`,
  `nsb_bpcal`, `nsb_lcal`.

- **`plot_leakage_footprint.py`** — Generates beam-layout footprint heatmaps
  from the leakage cube.
  - Multi-panel plots: 2 rows (bpcal / lcal) × N_odc columns, one PNG per
    reference field.
  - Single-panel plots: one PNG per (field, ODC, variant) combination —
    linked from the summary table rows on the HTML index page.
  - Validates footprint consistency across all SB_REFs before plotting.
  - Fixed colour scale 0–1.5 %, RdYlGn_r colourmap.
  - Beam labels: **B0**–**B35** (bold) with dL value underneath.

### HTML report (`build_phase3_html_report.py`)

- **Index page simplified**: inline summary tables (9 columns) for
  "Bandpass calibrated" and "Bandpass + Leakage (on-axis) calibrated"
  variants. Score-viewer pages removed.
- **Footprint heatmaps section**: per-field links to multi-panel footprint
  PNGs.
- **Clickable field names**: each table row's "Reference field" cell links to
  the individual footprint PNG for that (field, ODC, variant).
- **3D Leakage cube section**: describes the NetCDF4 cube (dimensions,
  variables, usage) with a download link. Raw beam-level CSVs listed as
  supporting data.
- **Column descriptions updated**:
  - "ODC calibration weight setting" → "ODC WEIGHTS ID"
  - "Reference calibration field" → "Name (with skyPos) of the field used
    for calibration"
  - n_obs(f) description clarified per ODC weight.
  - dL definition added: `dL = 100 × L/I`.
  - Notation convention note (superscript = aggregation dimension).
  - "Regular" → "Bandpass calibrated"; "Lcal" → "Bandpass + Leakage
    (on-axis) calibrated".

### Venv / dependencies

- Added `.venv` (Python 3.9.6) with: xarray 2024.7.0, netCDF4 1.7.2,
  pandas 2.3.3, numpy 2.0.2, matplotlib 3.9.4.
