# Changelog

All notable changes to this project are documented in this file.

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
