# Changelog

All notable changes to this project are documented in this file.

## 3.12 — 2026-03-19

Wires dQ/dU vs beam plots directly into the HTML report builder so the report
is fully self-contained. Clarifies and unifies `--html-only` / `--force` flag
behaviour across all plot-generation steps.

### Added
- `build_phase3_html_report.py` — `generate_dq_beam_plots()`: calls
  `plot_dQ_vs_beam.py --variant both --dU` as a subprocess at report build
  time; per-file skip-if-exists (delegates to `plot_dQ_vs_beam.py`); `--force`
  propagated to regenerate all plots.
- `build_phase3_html_report.py` — `dQ∿` and `dU∿` badges in the
  `ref_fieldname` table cell (badges 5 and 6), linking to
  `dQ_vs_beam_<field>_<variant>.png` and `dU_vs_beam_<field>_<variant>.png`
  respectively; `∿` (U+223F sine-wave) chosen as the line-plot symbol.
- `plot_dQ_vs_beam.py` — `--force` flag: regenerates all PNGs even if they
  already exist on disk.
- `plot_dQ_vs_beam.py` — per-file existence check inside the main loop:
  reconstructs the output filename and skips `make_figure()` if the PNG is
  already present and `--force` is not set.

### Changed
- `build_phase3_html_report.py` — unified `--html-only` / `--force` semantics:
  - `--html-only` now gates **all** plot-generation steps (upstream pipeline,
    PAF overlays, PAF movies, dQ/dU plots). Only HTML is rebuilt; all
    subprocesses are suppressed. PAF overlay/movie info is still collected
    via a disk-discovery pass (no subprocesses) to populate report links.
  - `--force` (without `--html-only`) regenerates every step unconditionally.
  - `--force` + `--html-only`: `--html-only` wins — no subprocesses run.

## 3.11 — 2026-03-19

Adds per-beam dQ (fractional Stokes-Q leakage) diagnostic plots and a
self-contained KaTeX document deriving the bandpass gain calibration strategy;
both are linked from the HTML report.

### Added
- `plot_dQ_vs_beam.py`: per-field line plots of dQ (and optionally dU) vs beam
  number per SB_REF; manifest-driven (same `--manifest`, `--start-index`,
  `--end-index`, `--exclude-indices` pattern as phase-1); `--fields` partial
  case-insensitive filter; `--variant both|regular|lcal`; smart y-axis —
  floor ±2.5%, expands to `max(ylim, |data| × 1.1)` if data exceed the floor;
  output filenames `dQ_vs_beam_<field>_<variant>.png`.
- `run_dQ_plots.sh`: example run script for `plot_dQ_vs_beam.py`; symlinked
  from `scratch/`; canonical `SCRIPTS` path resolution.
- `write_gain_calibration_strategy.py`: self-contained KaTeX HTML document
  deriving the bandpass gain calibration strategy in five sections
  (§1 initial measurement, §2 interim calibration, §3 1934−638 analysis,
  §4 exact solution for $G_x^{ic}$/$G_y^{ic}$ with explicit flux-scale caveat,
  §5 final voltage-gain table update). Can be run standalone or imported via
  `generate(path)`.

### Changed
- `build_phase3_html_report.py`: calls `write_gain_calibration_strategy.generate()`
  at build time, writing `gain_calibration_strategy.html` alongside `index.html`;
  adds a *Gain Calibration Strategy* link in the Run summary section.

## 3.10 — 2026-03-17

Adds a polarised-source catalog overlay to PAF plots, wires it through the HTML report builder, hardens all run scripts for symlink-safe execution, and restructures the HTML report layout — inline media pop-downs in summary tables, compact footprint badge links, and a cleaner single-page design.

### Added
- `fetch_pol_catalogs.py`: multi-catalog download and local CSV cache — priority chain POSSUM AS203 (CASDA) → Taylor 2009 (VizieR) → ATNF pulsar catalog; CASDA credentials via `CASDA_USER`/`CASDA_PASSWORD` env vars or `~/.netrc`; `--refresh` to force re-download; `--cone-radius` for source selection.
- `paf_port_layout.py` — `draw_pol_sources()`: overlays polarised sources on PAF diagrams with flux-scaled markers, RM-coloured (RdBu) fill, and optional fractional-polarisation highlight rings (YlOrRd); mplcursors hover tooltips showing source name, flux, RM, and frac-pol.
- `plot_paf_beam_overlay.py` / `plot_paf_beam_movie.py`: new flags `--pol-sources`, `--highlight-frac-pol <threshold>`, `--catalog-dir`, `--cone-radius`, `--show`.
- `run_html_report.sh`: canonical local entry point for HTML report generation; all CLI options documented inline; uses `python3` realpath for symlink-safe `SCRIPTS` resolution; activates `.venv`; `--html-only` quick-rebuild block added.

### Changed
- `build_phase3_html_report.py` — HTML layout restructured:
  - Per-SB_REF media (▶ IQUV, ⊞ IQUV, ▶ dP, ⊞ dP, 📈 beamwise, 🖼 PAF, ▶ PAF) moved inline into summary tables as compact floating pop-down menus (click trigger, Esc/click-away to dismiss); no page reflow.
  - `ref_fieldname` cell gains four footprint badges: `dL` / `|dQ|,|dU|` (blue, per-ODC per-variant) and `dL≈` / `|dQ|,|dU|≈` (amber, all-ODC comparison with both variants stacked).
  - `Footprint heatmaps` section removed; badge legend note added above the summary tables.
  - `Downloads: GIF animations and combined-beams PDFs` section removed.
  - Scope docstring updated to reflect indices 14–49 excl. 24–29.
  - `--html-only` flag: skips all upstream pipeline steps and regenerates only `index.html`.
  - `--pol-sources`, `--catalog-dir`, and `--highlight-frac-pol` wired through to per-SB subprocess calls; `assemble_package()` now copies `plots/*.mp4`; `--force` flag.
  - `build_phase1_master_table.py` wired as step 1 of `run_upstream_pipeline()`; `--start-index`, `--end-index`, `--exclude-indices` args propagated end-to-end.
- All `run_*.sh` scripts: `SCRIPTS` resolved via `python3 -c 'import os, sys; ...'` for full symlink safety; venv activated only in local scripts.
- `scratch/run_*.sh`: replaced plain copies with symlinks to canonical repo scripts.

## 3.9 — 2026-03-16

Refactors PAF plot annotation and fixes the sky→PAF coordinate transform.

### Changed
- `paf_port_layout.py` / `plot_paf_beam_overlay.py`: shared annotation info-box driven by a metadata dict (SBID, field, pol_axis, frequency); eliminates duplicated annotation code across single and multi-panel plots.
- `paf_port_layout.py`: corrected sky→PAF transform — `pol_axis` rotation sign was inverted by 45°; fixed sky-view display orientation.
- `projects/calibration-updates-2026/README.md`: project workflow moved here from the top-level README; top-level README now points to it.

### Removed
- Obsolete helper scripts: `make_single_index_manifest`, `extract_ref_fieldnames`, `sb-to-field-mapping`.

## 3.8 — 2026-03-15

Adds an animated PAF beam-scan movie and integrates PAF overlays into the HTML report.

### Added
- `plot_paf_beam_movie.py`: renders an MP4 animation sweeping the closepack-36 beam footprint across the PAF element grid to simulate a beam scan; `--trail <n>` ghost frames, `--fps`, `--dpi`; `create_paf_beam_movie.sh` + `run_paf_beam_movie.sh` convenience wrappers.
- `build_phase3_html_report.py`: PAF beam-overlay PNGs and beam-scan MP4s embedded as collapsible cards per `SB_REF`; `--end-index` extended to cover full manifest range; `--combine-only` flag.

### Changed
- `paf_port_layout.py`: reduced PAF element fill alpha (active 0.28 → 0.08; inactive 0.07 → 0.03) so beam footprint circles are clearly visible against the element grid.

## 3.7 — 2026-03-15

Adds two PAF visualisation scripts and a minor fix to the HTML report.

### Added
- `paf_port_layout.py`: ASKAP MkII PAF layout library — 112-element 12×12
  symmetric grid (188 ports), compass-based sky→PAF transform
  (`pol_axis`-aware, rear-view, focal-plane inversion), FWHM beam circles,
  diagnostic sky-direction markers, and multi-panel `pol_axis` comparison
  plots.
- `plot_paf_beam_overlay.py`: CLI tool — overlays closepack-36 beam footprint
  on the MkII PAF element grid; auto-reads pol_axis, SBID, and centre
  frequency from the schedblock file; beam radius derived from `1.02 λ/D`;
  diamond-needle compass rose (N=red); optional sky-source diagnostic stars
  (`--sky-markers`).

### Fixed
- `build_phase3_html_report.py`: semi-transparent cmap-sampled colours for
  Q/U footprint legend wedges.

## 3.6 — 2026-03-13

Extends the leakage-diagnostics pipeline with full Q/U decomposition across
every layer: isolation tables → cube → footprint plots → HTML report.

### Added
- `build_phase2_isolation_tables.py`: propagate `leak_q_over_i_pct` /
  `leak_u_over_i_pct` into beam×field and field-scores tables
  (`median_q_over_i`, `p90_q_over_i`, beam-level aggregates).
- `build_leakage_cube.py`: four new cube variables `dQ_regular`, `dQ_lcal`,
  `dU_regular`, `dU_lcal` (|Q|/I × 100 % and |U|/I × 100 %).
- `plot_leakage_footprint.py`: split-circle Q/U footprint plots with 45°
  diagonal split and real `Wedge`-patch legend; single-panel and
  combined-heatmap variants.
- `build_phase3_html_report.py`:
  - Merged L + Q/U footprint overview into a single field-row table.
  - Per-(ODC, variant) Q/U badge in each summary-table row.
  - `leakage_stats` PNG as **📈 beamwise** button in Pol. degree card cells.
  - Uniform 26 px button height; blue/green/blue/green colour scheme.
  - Labels: "Stokes spectra"→"Stokes"; "6×6 grid"→"⊞ all beams";
    section renamed "Leakage statistics for beams (per SB_REF)".
  - `assemble_package()` + `--package <path>` CLI flag: builds a
    self-contained shareable directory (plots, media PNGs + MP4s, cube,
    patched `index.html` with GIFs and CSV sections stripped).
- `convert_pdfs_to_png.py` (new untracked utility): pre-renders
  `combined_beams` PDF pages to PNG for embeds in the HTML report.

## 3.5 — 2026-03-11

Patch update prepared on `develop` and intended for the next release tag.

### Fixed
- `-insituPreflags` directory suffix logic now depends only on `DO_PREFLAG_REFTABLE=true` (no dependency on `AMP_STRATEGY` being set).
- Applied consistently across:
  - `projects/calibration-updates-2026/slurm/start_refField.slurm`
  - `projects/calibration-updates-2026/slurm/start_1934s.slurm`
  - `projects/calibration-updates-2026/scripts/assess_possum_1934s.sh`
  - `projects/calibration-updates-2026/scripts/copy_and_combine_assessment_results.sh`

### Changed
- Project docs updated to clarify that `insituPreflags` is controlled by preflag state only.

## 3.4 - 2026-03-11

Patch release focused on strict strategy parsing and safer operator validation for stage-1/stage-2.

### Added
- `--dry-run-parse` option in:
  - `projects/calibration-updates-2026/slurm/start_refField.slurm`
  - `projects/calibration-updates-2026/slurm/start_1934s.slurm`
- Parse mode prints effective per-index tuple values after global defaults and row-level overrides:
  - `ODC_WEIGHT`
  - `AMP_STRATEGY`
  - `DO_PREFLAG_REFTABLE`

### Changed
- Manifest optional row tokens in stage-1/stage-2 SLURM scripts are now strict `KEY=VALUE`.
- Unknown or malformed optional tokens now fail fast with explicit errors.
- Added early `-h/--help` handling in both SLURM scripts.
- Added `sh`-safe bootstrap (`exec /bin/bash`) for both SLURM scripts to avoid shell-compatibility issues.

### Fixed
- Row-level `ODC_WEIGHT=...` now deterministically overrides global default values for the corresponding tuple.
- Removed ambiguous positional-token behavior that could misinterpret strategy values.
- `--dry-run-parse` now runs without requiring HPC module environment setup.

## 3.2 - 2026-03-10

Production release focused on stage-4 usability and clearer operator documentation.

### Added
- Native manifest row filtering for stage-4 copy/combine via:
  - `--start-index`
  - `--end-index`
  in `projects/calibration-updates-2026/scripts/copy_and_combine_assessment_results.sh`
- Stage-4 helper now includes direct single-index example usage:
  - `projects/calibration-updates-2026/scripts/run_stage-4.sh`

### Changed
- Main onboarding documentation in `README.md` is expanded to clearly describe:
  - strict stage order and dependency chain
  - which stages run on HPC vs local machine
  - explicit script references for stages 1-4 (SLURM + shell wrappers)
  - direct linkage between assessment outputs and `mstool/bin/combine_beam_outputs.py`
  - guidance for users other than `raj030` to adapt remote/local paths and access

### Fixed
- Reduced ambiguity in stage-4 usage by documenting exact script entry points and execution context.

## 3.3 - 2026-03-10

Release focused on flexible stage-4 row selection for copy+combine.

### Added
- `--exclude-indices` support in
  - `projects/calibration-updates-2026/scripts/copy_and_combine_assessment_results.sh`
- Exclusion syntax supports:
  - single index (e.g. `29`)
  - contiguous range (e.g. `24-29`)
  - comma-separated combinations (e.g. `24-29,31,33-35`)

### Changed
- Stage-4 manifest filtering now supports include range plus explicit exclusions in one run.
- Project README examples updated to show stage-4 exclusion usage.

## 3.0 - 2026-03-10

Major refactor of the calibration-updates workflow and manifest model since the 2.x series.

### What 3.0 does that 2.x does not
- Introduces `averageMS.py`-driven assessment output generation as an explicit workflow stage (stage-3), instead of only post-copy aggregation.
- Adds a complete 4-stage operational flow (`refField -> 1934 -> assessment -> local copy+combine`) with ready-to-run stage wrappers.
- Treats `projects/calibration-updates-2026/scripts/*` as calibration-project orchestration helpers (project-specific), while core reusable ASKAP tooling remains under `mstool/bin`.
- Requires strict manifest optional tokens using explicit keys (`ODC_WEIGHT`, `AMP_STRATEGY`, `DO_PREFLAG_REFTABLE`, `REF_FIELDNAME`) for deterministic parsing.

### Breaking changes
- Enforced strict `KEY=VALUE` format for optional manifest row tokens in project scripts.
- Unkeyed optional tokens are now rejected for row-level strategy values.
- Workflow documentation and helpers now assume explicit 4-stage execution:
  1) refField processing
  2) 1934 processing
  3) assessment generation
  4) local copy+combine

### Added
- New assessment orchestration script:
  - `projects/calibration-updates-2026/scripts/assess_possum_1934s.sh`
  - Manifest-driven tuple parsing with index selection and beam-range controls.
  - `--dry-run` support.
- New REF field-name extraction helper:
  - `projects/calibration-updates-2026/scripts/extract_ref_fieldnames_from_manifest.sh`
  - Reads manifest SB_REFs and queries `schedblock` to generate field-name mapping.
  - Handles multiple targets (`Multi`) and includes conditional HPC module bootstrap for `schedblock`.
- New stage convenience wrappers:
  - `projects/calibration-updates-2026/scripts/run_stage-1.sh`
  - `projects/calibration-updates-2026/scripts/run_stage-2.sh`
  - `projects/calibration-updates-2026/scripts/run_stage-3.sh`
  - `projects/calibration-updates-2026/scripts/run_stage-4.sh`

### Changed
- Plot headers enhanced in:
  - `mstool/bin/averageMS.py`
  - `mstool/bin/combine_beam_outputs.py`
- Added third header row for `SB_REF FIELD_NAME`.
- If field-name cannot be resolved, a blank reserved row is retained.
- Manifest model updated to explicit optional keys:
  - `ODC_WEIGHT=...`
  - `AMP_STRATEGY=...`
  - `DO_PREFLAG_REFTABLE=...`
  - `REF_FIELDNAME=...`
- Full `REF_FIELDNAME` population added to
  - `projects/calibration-updates-2026/manifests/sb_manifest_reffield_average.txt`
  using extracted mapping data.
- Project and root workflow docs updated for stage linkage and strict manifest usage.

### Fixed
- Robust path/module behavior improvements for HPC execution context in newly added helper scripts.
- More explicit diagnostics for malformed manifest rows and token parsing issues.

## 2.1
- Previous 2.x baseline release.

## 2.0
- Previous 2.x baseline release.
