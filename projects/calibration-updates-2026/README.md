# Calibration updates (reference fields) — 2026

This folder contains project-specific helper assets for the calibration update workflow using reference (read calibrator) fields.

## Layout

- `scripts/` : project helper scripts
- `manifests/` : SB/ODC manifest files for copy+combine runs
- `slurm/` : batch job scripts for Setonix

Convenience wrappers in `scripts/` (run from `~/mstool/scratch`):

- `run_stage-1.sh` (submit stage `ref` for idx=2)
- `run_stage-2.sh` (submit stage `1934` for idx=2)
- `run_stage-3.sh` (run assessment for idx=2)
- `run_stage-4.sh` (run copy+combine locally for idx=2)

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

- `_AMP_STRATEGY-<value>-insituPreflags` only when `DO_PREFLAG_REFTABLE=true`
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

Recommended run order:

1. Reference-field processing (generate bandpass/leakage tables)
2. 1934 processing (consumes the generated tables)
3. Run assessment script (generate per-beam assessment plots/txt on HPC)
4. Copy + combine assessment outputs (can be run locally once steps 1-3 are done)

Example sequence:

```bash
cd ~/mstool/scratch

sbatch ../projects/calibration-updates-2026/slurm/start_refField.slurm \
  --manifest ../projects/calibration-updates-2026/manifests/sb_manifest_reffield_average.txt

sbatch ../projects/calibration-updates-2026/slurm/start_1934s.slurm \
  --manifest ../projects/calibration-updates-2026/manifests/sb_manifest_reffield_average.txt

../projects/calibration-updates-2026/scripts/assess_possum_1934s.sh \
  --manifest ../projects/calibration-updates-2026/manifests/sb_manifest_reffield_average.txt

../projects/calibration-updates-2026/scripts/copy_and_combine_assessment_results.sh \
  --manifest ../projects/calibration-updates-2026/manifests/sb_manifest_reffield_average.txt
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
cd ~/github-wasimraja81/mstool
cd scratch

TMP_MANIFEST=/tmp/mstool_manifest_idx2.txt

../projects/calibration-updates-2026/scripts/make_single_index_manifest.sh \
  --index 2 \
  --output "$TMP_MANIFEST"

../projects/calibration-updates-2026/scripts/copy_and_combine_assessment_results.sh \
  --manifest "$TMP_MANIFEST"
```

Stage-4 now also supports direct manifest row filtering:

```bash
../projects/calibration-updates-2026/scripts/copy_and_combine_assessment_results.sh \
  --manifest ../projects/calibration-updates-2026/manifests/sb_manifest_reffield_average.txt \
  --start-index 2 --end-index 2
```

## Notes

- Core reusable ASKAP visibility tooling remains in `mstool/bin` and `mstool/src`.
- These project files are intentionally kept outside the installable package entry points defined in `setup.py`.