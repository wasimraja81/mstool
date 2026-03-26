# Calibration updates (reference fields) — 2026

> **New to the pipeline?** Start with the [Getting Started guide](https://wasimraja81.github.io/mstool/projects/calibration-updates-2026/docs/getting-started.html) — a step-by-step walkthrough from stage 1 through to publishing the report.

> **Current release: tag `4.0`** — New [Getting Started guide](https://wasimraja81.github.io/mstool/projects/calibration-updates-2026/docs/getting-started.html); path-independence fixes for `run_paf_beam_movie.sh` and `run_paf_beam_overlay.sh`; documentation accuracy pass (`ref_ws` terminology, manifest format, code example paths).

This project measures and analyses on-axis polarisation leakage across ASKAP
beams, reference fields, and ODC calibration-weight configurations.  It drives
a four-stage pipeline (stages 1–3 on HPC, stage 4 locally) using a shared
manifest file that maps each scheduling block tuple to its processing
parameters.  Post-pipeline diagnostics produce a self-contained HTML leakage
report, NetCDF4 leakage cube, footprint heatmaps, per-SB_REF PAF overlay
images, and Airy-disk beam-scan animation MP4s.

## Layout

```
projects/calibration-updates-2026/
  manifests/   SB/ODC manifest files (sb_manifest_reffield_average.txt)
  scripts/     pipeline orchestration, diagnostics, and visualisation scripts
  slurm/       SLURM batch scripts for Setonix (start_refField.slurm, start_1934s.slurm)
  metadata/    README describing the metadata/ directory convention
```

## Pipeline stages

Run order is strict.  All stages accept `--manifest FILE --start-index N --end-index N [--exclude-indices SPEC]`.

| Stage | Where | Script | Purpose |
|-------|-------|--------|---------|
| 1 — refField | HPC | `slurm/start_refField.slurm` / `run_stage-1.sh` | Generate bandpass + leakage tables from reference-field observations |
| 2 — 1934 | HPC | `slurm/start_1934s.slurm` / `run_stage-2.sh` | Apply tables to 1934 data; quality-check on-axis calibration |
| 3 — assessment | HPC | `assess_possum_1934s.sh` / `run_stage-3.sh` | Run `averageMS.py` assessment; produce per-beam `.txt` / `.lcal.txt` channel files and PNG plots |
| 4 — copy + combine | Local | `copy_and_combine_assessment_results.sh` / `run_stage-4.sh` | Copy HPC outputs locally; invoke `combine_beam_outputs.py`; copy metadata. If only `.txt`/`.lcal.txt` files are available (PNGs not copied), pass `--regen-beam-pngs` to regenerate PNGs locally before combining — **no HPC access or measurement sets needed** |

### Quick start

From `~/mstool/scratch` (all stages accept `--manifest`, `--start-index`, `--end-index`, `--exclude-indices`):

```bash
# Stage 1 (HPC)
../projects/calibration-updates-2026/scripts/run_stage-1.sh

# Stage 2 (HPC)
../projects/calibration-updates-2026/scripts/run_stage-2.sh

# Stage 3 (HPC)
../projects/calibration-updates-2026/scripts/run_stage-3.sh

# Stage 4 (local) — copy results + metadata, combine per-beam outputs
../projects/calibration-updates-2026/scripts/run_stage-4.sh
```

### Manual commands

```bash
# Stage 1 (HPC) — adjust --start-index/--end-index for subset runs
sbatch projects/calibration-updates-2026/slurm/start_refField.slurm \
  --manifest projects/calibration-updates-2026/manifests/sb_manifest_reffield_average.txt \
  --start-index 14 --end-index 42 --exclude-indices 24-29

# Stage 2 (HPC)
sbatch projects/calibration-updates-2026/slurm/start_1934s.slurm \
  --manifest projects/calibration-updates-2026/manifests/sb_manifest_reffield_average.txt \
  --start-index 14 --end-index 42 --exclude-indices 24-29

# Stage 3 (HPC)
projects/calibration-updates-2026/scripts/assess_possum_1934s.sh \
  --manifest projects/calibration-updates-2026/manifests/sb_manifest_reffield_average.txt \
  --start-index 14 --end-index 42 --exclude-indices 24-29

# Stage 4 (local) — also copies metadata/ directories
projects/calibration-updates-2026/scripts/copy_and_combine_assessment_results.sh \
  --manifest projects/calibration-updates-2026/manifests/sb_manifest_reffield_average.txt \
  --start-index 14 --end-index 42 --exclude-indices 24-29 --copy-metadata

# Single SB_REF test (e.g. idx=16 = SB_REF 81084)
projects/calibration-updates-2026/scripts/copy_and_combine_assessment_results.sh \
  --manifest projects/calibration-updates-2026/manifests/sb_manifest_reffield_average.txt \
  --start-index 16 --end-index 16
```

### Porting to a new user environment

Override via manifest `KEY=VALUE` entries and CLI arguments rather than hard-coding paths:

- `REMOTE` — your HPC login/host
- `REMOTE_BASE_ROOT` and ODC paths matching your project storage
- `LOCAL_BASE` — your local destination directory
- Any module/environment requirements for `schedblock`/ASKAP tooling

### Leakage diagnostics pipeline

Post-processing scripts for analysing residual on-axis polarisation leakage
across beams, reference fields, and ODC weights:

| Script | Purpose |
|--------|---------|
| `build_phase1_master_table.py` | Build the Phase-1 master table from per-SB assessment outputs |
| `build_phase2_isolation_tables.py` | Produce Phase-2 beam×field and beam×ODC isolation CSVs |
| `build_leakage_cube.py` | Construct a 3-D NetCDF4 cube (beam × field × odc) from the Phase-2 CSV |
| `plot_leakage_footprint.py` | Generate beam-layout footprint heatmaps from the cube |
| `build_phase3_html_report.py` | Run full pipeline end-to-end: summary tables, footprint links, per-SB_REF PAF beam-overlay plots, cube download. Calls `plot_dQ_vs_beam.py` to generate dQ∿/dU∿ per-field line-plot PNGs and links them as badges in the summary table. Generates `gain_calibration_strategy.html` alongside `index.html`. Supports `--package <path>` for a self-contained shareable directory. `--html-only` skips all subprocesses (uses existing PNGs); `--force` regenerates everything. |

### dQ diagnostics and gain calibration strategy

| Script | Purpose |
|--------|---------|
| `plot_dQ_vs_beam.py` | Per-field line plots of dQ (and dU with `--dU`) vs beam number per SB_REF; manifest-driven; `--fields` partial filter; smart ylim (floor ±2.5%, auto-expands); `--variant both\|bpcal\|lcal`; thick mean line (cross-observation mean per beam) overlaid on each plot; writes `dq_du_correction_factors.txt` lookup table (fixed-width ASCII: field, variant, beam, mean\_dQ, std\_dQ, mean\_dU, std\_dU, n\_obs); per-file skip-if-exists; `--force` to regenerate. Called automatically by `build_phase3_html_report.py`. |
| `run_dQ_plots.sh` | Example run script for `plot_dQ_vs_beam.py`; symlinked from `scratch/` |
| `write_gain_calibration_strategy.py` | Generates `gain_calibration_strategy.html` — a self-contained KaTeX document with the full bandpass gain calibration derivation (§1–§5). Run standalone or call `generate(path)` from the report builder. |

### PAF beam-overlay visualisation

Scripts for visualising ASKAP MkII PAF element layouts and beam footprints:

| Script | Purpose |
|--------|---------|
| `paf_port_layout.py` | 112-element PAF layout library: port numbering, compass-based sky→PAF transform, multi-panel `pol_axis` comparison plots |
| `plot_paf_beam_overlay.py` | CLI tool: overlay a closepack-36 beam footprint on the 112-element PAF grid; auto-reads `pol_axis` and centre frequency from schedblock |
| `plot_paf_beam_movie.py` | Generate an Airy-disk beam-scan animation (MP4): one frame per beam, optional trail accumulation, display gamma, configurable nulls/cmap/fps |
| `create_paf_beam_movie.sh` | Manifest-driven wrapper: loops over selected rows, resolves `metadata/` paths using per-row `AMP_STRATEGY` + `DO_PREFLAG_REFTABLE`, calls `plot_paf_beam_movie.py` |
| `run_paf_beam_movie.sh` | Convenience caller: hardcoded manifest path + canonical index range; edit and run directly |

Example usage:

```bash
python scripts/plot_paf_beam_overlay.py \
  --footprint path/to/footprintOutput-sb81084-REF_0324-28.txt \
  --schedblock path/to/schedblock-info-81084.txt \
  --output /tmp/paf_overlay.png

# Add diagnostic star markers for validation
python scripts/plot_paf_beam_overlay.py ... --sky-markers
```

Beam-scan movie (run from repo root):

```bash
# Single SB_REF (quick test, no trail)
bash projects/calibration-updates-2026/scripts/create_paf_beam_movie.sh \
  --manifest projects/calibration-updates-2026/manifests/sb_manifest_reffield_average.txt \
  --start-index 16 --end-index 16 --trail 0

# All active SB_REFs (indices 14-42, skipping ODC-5233 24-29)
bash projects/calibration-updates-2026/scripts/run_paf_beam_movie.sh
```

Typical workflow (run from repo root with `.venv` activated):

```bash
source .venv/bin/activate

# Single command: runs Phase 1 → 2 → Cube → Footprint plots → PAF overlays → HTML report
# Add --package to also assemble a self-contained shareable copy
python projects/calibration-updates-2026/scripts/build_phase3_html_report.py \
  --data-root ~/DATA/reffield-average \
  --package ~/DATA/reffield-average/phase4-share

# Serve the report locally
python -m http.server 8765 -d ~/DATA/reffield-average/phase3
```

Output artefacts (under `~/DATA/reffield-average/`):

- `phase2/leakage_cube.nc` — 3-D labelled NetCDF4 cube (xarray-compatible); variables: `dL`, `dQ`, `dU`, `p90`, `nsb` × {bpcal, lcal}
- `phase3/index.html` — self-contained HTML report
- `phase3/plots/footprint_dL_*.png` — dL = √(Q²+U²)/I footprint heatmap PNGs (multi-panel and single-panel)
- `phase3/plots/footprint_QU_*.png` — split-circle Q/U footprint PNGs (multi-panel and per-(ODC, variant))
- `phase3/plots/paf_overlay_<SB_REF>.png` — per-SB_REF PAF port/beam overlay plots (generated from `metadata/`)
- `phase3/plots/paf_beam_movie_<SB_REF>.mp4` — per-SB_REF Airy-disk beam-scan animation (generated by `create_paf_beam_movie.sh`)
- `phase3/tables/` — CSV tables and interactive viewers
- `phase4-share/` — self-contained shareable package (plots + media PNGs/MP4s + cube; no GIFs/PDFs)
- `final_mvp_share/` — published copy synced to GitHub Pages (see below)

## Publishing the report to GitHub Pages

`scripts/publish_report.sh` syncs the assembled package to the public GitHub Pages repo ([wasimraja81/askap-leakage-report](https://github.com/wasimraja81/askap-leakage-report)) so colleagues can view the live report at:

> **https://wasimraja81.github.io/askap-leakage-report/**

### One-time setup

1. Make sure the GitHub repo exists and is public: `git@github.com:wasimraja81/askap-leakage-report.git`
2. Enable GitHub Pages: repo Settings → Pages → Source: **main branch / root** → Save.

### Publish workflow

```bash
# 1. Build the report package (run from mstool/scratch)
../projects/calibration-updates-2026/scripts/run_html_report.sh
# This writes the package to ~/DATA/reffield-average/final_mvp_share/

# 2. Push the package to the 'develop' branch of askap-leakage-report
bash projects/calibration-updates-2026/scripts/publish_report.sh

# 3. Go live: merge develop → main on GitHub
#    (PR or: git checkout main && git merge develop && git push, in ~/github-wasimraja81/askap-leakage-report)
#    GitHub Pages redeploys automatically (~1–3 min).
```

On **first run** the script clones the repo, creates the `develop` branch, and pushes. On **subsequent runs** it pulls, rsyncs, commits with a timestamp, and pushes.

### Branch convention

| Branch | Purpose |
|--------|---------|
| `develop` | Staging — `publish_report.sh` always pushes here |
| `main` | Live — GitHub Pages serves from this branch; merge `develop → main` to update |

## Main workflow helper

- Project path:
  - `projects/calibration-updates-2026/scripts/copy_and_combine_assessment_results.sh`

Example:

```bash
cd ~/mstool/scratch
../projects/calibration-updates-2026/scripts/copy_and_combine_assessment_results.sh \
  --manifest ../projects/calibration-updates-2026/manifests/sb_manifest_reffield_average.txt
```

## Assessment helper

- Script path:
  - `projects/calibration-updates-2026/scripts/assess_possum_1934s.sh`
- Uses the same tuple manifest format and index slicing controls as the SLURM scripts.
- Supports optional per-row `REF_FIELDNAME=<name>` for SB_REF plot headers.

Example (single tuple and limited beams):

```bash
cd ~/mstool/scratch
../projects/calibration-updates-2026/scripts/assess_possum_1934s.sh \
  --manifest ../projects/calibration-updates-2026/manifests/sb_manifest_reffield_average.txt \
  --start-index 2 --end-index 2 \
  --beam-start 0 --beam-end 3 \
  --dry-run
```

`--dry-run` validates manifest parsing and tuple/SB path checks, and prints planned actions without running `averageMS.py`.

`REF_FIELDNAME` resolution order in `assess_possum_1934s.sh`:

1. Use per-row manifest value when provided (recommended).
2. Otherwise, on HPC, try `schedblock info -p <SB_REF>` and resolve `common.targets` + `common.target.<src>.field_name`.
3. If multiple targets are present, set field label to `Multi` and print a warning.
4. If unresolved, keep a blank third header row on plots.

## Per-beam PNG regeneration (`regen_beam_pngs.py`)

`mstool/bin/regen_beam_pngs.py` is a **standalone** and **importable** tool that regenerates the per-beam Stokes and polarisation-degree PNG plots from the `.txt` / `.lcal.txt` channel files produced by `averageMS.py` — **no measurement sets or HPC access required**.

This means the full stage-4 workflow (combining outputs, generating the PDF report, leakage diagnostics) can run on a local machine as long as the `.txt` and `.lcal.txt` files are available locally.

### How field names are resolved

`averageMS.py` now writes `# Field Name: <name>` in the `.txt` file header whenever `--field-name` is passed (i.e. for all files produced by `assess_possum_1934s.sh`). For older files that pre-date this change, `regen_beam_pngs.py` falls back to a manifest lookup using the `REF_FIELDNAME=` token on the matching row.

### CLI usage

```bash
# Regenerate from a single file (auto-detects output dir = same dir as input)
python mstool/bin/regen_beam_pngs.py path/to/scienceData...beam08.txt

# Regenerate all beams in a directory, write PNGs to a specific output dir
python mstool/bin/regen_beam_pngs.py ~/DATA/reffield-average/SB_REF-81084.../assessment_results/ \
  --output-dir /tmp/regen_pngs/

# Specify manifest for field-name lookup on older .txt files
python mstool/bin/regen_beam_pngs.py path/to/assessment_results/ \
  --manifest projects/calibration-updates-2026/manifests/sb_manifest_reffield_average.txt

# Overwrite existing PNGs (default is skip-if-exists)
python mstool/bin/regen_beam_pngs.py path/to/ --overwrite

# Override ylim for the pol-degree panel (default ±5 %, matching the HPC pipeline)
python mstool/bin/regen_beam_pngs.py path/to/ --ylim-pol -3 3
```

### Integration with `combine_beam_outputs.py`

`combine_beam_outputs.py` supports an integrated regen pass via:

| Flag | Default | Description |
|------|---------|-------------|
| `--regen-beam-pngs` | off | Regenerate missing per-beam PNGs from `.txt` files before combining |
| `--regen-overwrite` | off | Also overwrite existing PNGs during regen |
| `--regen-ylim-pol YMIN YMAX` | `-5 5` | ylim for pol-degree panel (matches HPC pipeline) |
| `--regen-manifest PATH` | — | Manifest path for field-name lookup on older files |

Example (stage-4 invocation with regen enabled):

```bash
python mstool/bin/combine_beam_outputs.py \
  --output-dir ~/DATA/reffield-average/SB_REF-81084.../assessment_results/ \
  --regen-beam-pngs \
  --regen-manifest projects/calibration-updates-2026/manifests/sb_manifest_reffield_average.txt
```

### Running stage 4 locally from `.txt` files only

If you copied only the `.txt` and `.lcal.txt` files from HPC (not the PNGs), this is the recommended stage-4 invocation via the wrapper script:

```bash
cd ~/mstool/scratch
../projects/calibration-updates-2026/scripts/run_stage-4.sh \
  --manifest ../projects/calibration-updates-2026/manifests/sb_manifest_reffield_average.txt \
  --start-index 16 --end-index 16 \
  --regen-beam-pngs \
  --regen-manifest ../projects/calibration-updates-2026/manifests/sb_manifest_reffield_average.txt
```

The regen step runs once per `.txt` file, skips beams that already have PNGs, and is effectively a no-op if all PNGs are present.

## Manifest-driven SLURM processing

Both SLURM scripts now read the same tuple manifest used by the copy/combine helper.

Default manifest path used by both:

- `projects/calibration-updates-2026/manifests/sb_manifest_reffield_average.txt`

Manifest strategy controls are separated:

- `AMP_STRATEGY` (e.g. `multiply`, `keep`, `replace`)
- `DO_PREFLAG_REFTABLE` (`true`/`false`)

In stage-1 config generation, these map to:

- `BP_UPDATE_MODIFY_AMP_STRATEGY` ← `AMP_STRATEGY`
- `DO_PREFLAG_REFTABLE` / `APPLY_PREFLAGS_DIRECTLY_REFTABLE` ← `DO_PREFLAG_REFTABLE`

Directory naming keeps legacy behavior:

- append `-insituPreflags` whenever `DO_PREFLAG_REFTABLE=true` (independent of AMP strategy)
- no extra preflag suffix when `DO_PREFLAG_REFTABLE=false`

Example manifest rows:

```text
# Global defaults
AMP_STRATEGY=multiply
DO_PREFLAG_REFTABLE=true

# idx sb_ref sb_1934 sb_holo sb_target_1934 [optional tokens]
# Optional tokens are order-independent and must use key=value form
19 81099 77045 76554 81107 ODC_WEIGHT=5231
20 81100 77045 76554 81107 ODC_WEIGHT=5231 AMP_STRATEGY=multiply DO_PREFLAG_REFTABLE=false REF_FIELDNAME=REF_0336-32
```

Recommended optional row tokens:

- `ODC_WEIGHT=<id>` (or `ODC_WEIGHT_ID=<id>`, `ODC=<id>`)
- `AMP_STRATEGY=<value>`
- `DO_PREFLAG_REFTABLE=<true|false>` (or `DO_PREFLAG=<...>`)
- `REF_FIELDNAME=<name>`

Unkeyed optional tokens are rejected.

Expected tuple directory suffixes from the above:

- row 19 → `..._AMP_STRATEGY-multiply-insituPreflags`
- row 20 → `..._AMP_STRATEGY-multiply`

Optional arguments for both SLURM scripts:

- `--manifest <path>`
- `--start-index <i>`
- `--end-index <j>`

Quick checks:

```bash
cd ~/mstool/projects/calibration-updates-2026/slurm

# show usage (works with sh)
sh start_refField.slurm -h
sh start_1934s.slurm -h

# print resolved per-index ODC/AMP/PREFLAG (no fetch/processing)
bash start_refField.slurm --dry-run-parse --start-index 36 --end-index 49
bash start_1934s.slurm --dry-run-parse --start-index 36 --end-index 49
```

Recommended run order:

1. Reference-field processing (generate bandpass/leakage tables) — **HPC**
2. 1934 processing (consumes the generated tables) — **HPC**
3. Run assessment script — produces per-beam `.txt` / `.lcal.txt` channel files and PNG plots on **HPC**
4. Copy + combine assessment outputs — **local** once steps 1–3 are done.  If only `.txt`/`.lcal.txt` files were copied (no PNGs), pass `--regen-beam-pngs` to regenerate PNGs locally before combining (see [Per-beam PNG regeneration](#per-beam-png-regeneration-regen_beam_pngspy))

Example sequence:

```bash
cd ~/mstool/scratch

sbatch ../projects/calibration-updates-2026/slurm/start_refField.slurm \
  --manifest ../projects/calibration-updates-2026/manifests/sb_manifest_reffield_average.txt

sbatch ../projects/calibration-updates-2026/slurm/start_1934s.slurm \
  --manifest ../projects/calibration-updates-2026/manifests/sb_manifest_reffield_average.txt

../projects/calibration-updates-2026/scripts/assess_possum_1934s.sh \
  --manifest ../projects/calibration-updates-2026/manifests/sb_manifest_reffield_average.txt

# Standard: copy everything (PNGs + txt) then combine
../projects/calibration-updates-2026/scripts/copy_and_combine_assessment_results.sh \
  --manifest ../projects/calibration-updates-2026/manifests/sb_manifest_reffield_average.txt

# Alternative: copy only .txt/.lcal.txt files, regenerate PNGs locally
../projects/calibration-updates-2026/scripts/copy_and_combine_assessment_results.sh \
  --manifest ../projects/calibration-updates-2026/manifests/sb_manifest_reffield_average.txt \
  --regen-beam-pngs \
  --regen-manifest ../projects/calibration-updates-2026/manifests/sb_manifest_reffield_average.txt
```

Or use the submit helper (recommended on HPC clone):

```bash
cd ~/mstool/scratch

../projects/calibration-updates-2026/slurm/submit_pipeline.sh \
  --stage ref \
  --manifest ../projects/calibration-updates-2026/manifests/sb_manifest_reffield_average.txt

# Submit stage-2 separately only after stage-1 child pipeline jobs are complete
../projects/calibration-updates-2026/slurm/submit_pipeline.sh \
  --stage 1934 \
  --manifest ../projects/calibration-updates-2026/manifests/sb_manifest_reffield_average.txt
```

Single-case test only (to avoid broad remote load):

```bash
cd ~/mstool/scratch

../projects/calibration-updates-2026/slurm/submit_pipeline.sh \
  --stage ref \
  --manifest ../projects/calibration-updates-2026/manifests/sb_manifest_reffield_average.txt \
  --start-index 19 --end-index 19
```

### End-to-end example for `idx=2`

For a single tuple (legacy case `idx=2`), run stages 1-3 on HPC, then run stage-4 locally.

1) On remote HPC (from cloned repo): submit stage-1 for only `idx=2`

```bash
cd ~/mstool/scratch
../projects/calibration-updates-2026/slurm/submit_pipeline.sh \
  --stage ref \
  --manifest ../projects/calibration-updates-2026/manifests/sb_manifest_reffield_average.txt \
  --start-index 2 --end-index 2
```

2) On remote HPC: after stage-1 child pipeline jobs complete, submit stage-2 for only `idx=2`

```bash
cd ~/mstool/scratch
../projects/calibration-updates-2026/slurm/submit_pipeline.sh \
  --stage 1934 \
  --manifest ../projects/calibration-updates-2026/manifests/sb_manifest_reffield_average.txt \
  --start-index 2 --end-index 2
```

3) On remote HPC: run stage-3 (assessment) for only `idx=2`

```bash
cd ~/mstool/scratch
../projects/calibration-updates-2026/scripts/assess_possum_1934s.sh \
  --manifest ../projects/calibration-updates-2026/manifests/sb_manifest_reffield_average.txt \
  --start-index 2 --end-index 2
```

4) On local machine: run stage-4 (copy + combine) for only `idx=2`

```bash
../projects/calibration-updates-2026/scripts/copy_and_combine_assessment_results.sh \
  --manifest ../projects/calibration-updates-2026/manifests/sb_manifest_reffield_average.txt \
  --start-index 2 --end-index 2
```

**Local-only variant** — if you copied only the `.txt` / `.lcal.txt` channel files (not the PNGs), add `--regen-beam-pngs` to regenerate PNGs locally from the channel files before combining:

```bash
../projects/calibration-updates-2026/scripts/copy_and_combine_assessment_results.sh \
  --manifest ../projects/calibration-updates-2026/manifests/sb_manifest_reffield_average.txt \
  --start-index 2 --end-index 2 \
  --regen-beam-pngs \
  --regen-manifest ../projects/calibration-updates-2026/manifests/sb_manifest_reffield_average.txt
```

You can also exclude selected indices in stage-4:

```bash
../projects/calibration-updates-2026/scripts/copy_and_combine_assessment_results.sh \
  --manifest ../projects/calibration-updates-2026/manifests/sb_manifest_reffield_average.txt \
  --start-index 14 --end-index 35 \
  --exclude-indices 24-29,31,33-35
```

## Notes

- Core reusable ASKAP visibility tooling remains in `mstool/bin` and `mstool/src`.
- These project files are intentionally kept outside the installable package entry points defined in `setup.py`.

## Python dependencies (leakage diagnostics)

The diagnostic scripts require a virtual environment with:

| Package | Version |
|---------|---------|
| xarray | ≥ 2024.7 |
| netCDF4 | ≥ 1.7 |
| pandas | ≥ 2.0 |
| numpy | ≥ 1.24 |
| matplotlib | ≥ 3.8 |
| scipy | ≥ 1.10 |

Create with:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install xarray ne