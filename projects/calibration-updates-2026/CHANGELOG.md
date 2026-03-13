# Changelog — calibration-updates-2026

## 3.6 — 2026-03-13

### Pipeline: Q/U leakage diagnostics

- **`build_phase2_isolation_tables.py`** — extended to propagate per-SB
  `leak_q_over_i_pct` and `leak_u_over_i_pct` columns through both the
  beam×field and beam×ODC isolation tables. Adds `median_q_over_i`,
  `p90_q_over_i`, `median_u_over_i`, `p90_u_over_i` to beam×field rows and
  the corresponding beam-level aggregates to the field-scores table.

- **`build_leakage_cube.py`** — adds four new cube variables:
  `dQ_regular`, `dQ_lcal`, `dU_regular`, `dU_lcal`
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
  Variables: `dL_regular`, `dL_lcal`, `p90_regular`, `p90_lcal`,
  `nsb_regular`, `nsb_lcal`.

- **`plot_leakage_footprint.py`** — Generates beam-layout footprint heatmaps
  from the leakage cube.
  - Multi-panel plots: 2 rows (regular / lcal) × N_odc columns, one PNG per
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
