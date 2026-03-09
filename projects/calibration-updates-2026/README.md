# Calibration updates (reference fields) — 2026

This folder contains project-specific helper assets for the calibration update workflow using reference (read calibrator) fields.

## Layout

- `scripts/` : project helper scripts
- `manifests/` : SB/ODC manifest files for copy+combine runs
- `slurm/` : batch job scripts for Setonix

## Main workflow helper

- Project path:
  - `projects/calibration-updates-2026/scripts/copy_and_combine_assessment_results.sh`

Example:

```bash
./projects/calibration-updates-2026/scripts/copy_and_combine_assessment_results.sh \
  --manifest projects/calibration-updates-2026/manifests/sb_manifest_reffield_average.txt
```

## Notes

- Core reusable ASKAP visibility tooling remains in `mstool/bin` and `mstool/src`.
- These project files are intentionally kept outside the installable package entry points defined in `setup.py`.