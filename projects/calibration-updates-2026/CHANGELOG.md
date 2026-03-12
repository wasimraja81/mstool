# Changelog — calibration-updates-2026

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
