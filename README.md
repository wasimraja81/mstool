# mstool
This repository contains tools for ASKAP table analysis.

## Repository layout
* `mstool/bin` - reusable python scripts for ASKAP ms table query/analysis and continuum removal.
* `mstool/src` - Fortran codes for poly-harm fitting used for continuum removal per baseline per timestamp.
* `mstool/doc` - historical notes/presentations about mstool features.
* `projects/calibration-updates-2026` - project-specific helpers (manifests, slurm, orchestration scripts) for calibration updates using reference fields.

The required fortran libraries are built and the core scripts are installed in the system default directories with the fortran libraries properly linked.
### Python scripts 
MSTOOL comprises of the following python scripts: 
* `msInfo.py` - Query and print metadata information and tables from a measurement set.
* `remUVcont.py` - Remove continuum and artifacts from uv data.
* `fixDir.py` - Curate FEED and FIELD tables in ASKAP ms to make them CASA compatible.
* `sniffMS.py` - Query and print visibilities from ASKAP ms for a specified record, baseline, channelNum and polarisation.
* `sniffUVW.py` - Query and print UVW values from ASKAP ms for a specified baseline.

### building and installation
```
askapdev>$ git clone https://github.com/wasimraja81/mstool.git
askapdev>$ cd mstool
askapuser>$ pip3 install -e .
```
This will build the fortran libraries, and install the scripts in `/usr/local/bin` in a unix system.

### Run a test
```
askapuser>$ msInfo.py -h
```

### Project-specific workflow (calibration updates)

This calibration-update workflow is project-specific and lives under `projects/calibration-updates-2026`.

Run order is strict:

1) **refField processing** (must run first)
	 - Generates bandpass/leakage tables consumed by later stages.
	- SLURM script: `projects/calibration-updates-2026/slurm/start_refField.slurm`
	- Wrapper: `projects/calibration-updates-2026/scripts/run_stage-1.sh`
2) **1934 processing**
	 - Uses tables produced in stage-1.
	- SLURM script: `projects/calibration-updates-2026/slurm/start_1934s.slurm`
	- Wrapper: `projects/calibration-updates-2026/scripts/run_stage-2.sh`
3) **assessment processing**
	 - Runs `averageMS.py`-based assessment on 1934 outputs (quality check of on-axis calibration).
	- Script: `projects/calibration-updates-2026/scripts/assess_possum_1934s.sh`
	- Wrapper: `projects/calibration-updates-2026/scripts/run_stage-3.sh`
	- Produces per-beam assessment products consumed by `mstool/bin/combine_beam_outputs.py` in stage-4.
4) **combine outputs**
	- Produces summary products via `projects/calibration-updates-2026/scripts/copy_and_combine_assessment_results.sh`.
	- If you prefer wrappers, run `projects/calibration-updates-2026/scripts/run_stage-4.sh`.
	- This stage can run locally after stages 1-3 complete on HPC.
	- The combine engine is `mstool/bin/combine_beam_outputs.py`.
	- `copy_and_combine_assessment_results.sh` first copies assessment output directories from remote HPC to local, then invokes `combine_beam_outputs.py` per copied directory.

### Where each stage should run

- **HPC (Setonix/remote)**: stage-1, stage-2, stage-3
- **Local machine (optional)**: stage-4 using copy+combine after stages 1-3 complete on HPC

### Quick start with helper scripts

From `~/mstool/scratch`, helper wrappers are provided:

- `../projects/calibration-updates-2026/scripts/run_stage-1.sh`
- `../projects/calibration-updates-2026/scripts/run_stage-2.sh`
- `../projects/calibration-updates-2026/scripts/run_stage-3.sh`
- `../projects/calibration-updates-2026/scripts/run_stage-4.sh`

These wrappers demonstrate a minimal single-index flow (`idx=2`) and are intended as starter templates.

### Manual commands (explicit)

```bash
# Stage-1 (HPC)
sbatch ./projects/calibration-updates-2026/slurm/start_refField.slurm \
	--manifest ./projects/calibration-updates-2026/manifests/sb_manifest_reffield_average.txt

# Stage-2 (HPC)
sbatch ./projects/calibration-updates-2026/slurm/start_1934s.slurm \
	--manifest ./projects/calibration-updates-2026/manifests/sb_manifest_reffield_average.txt

# Stage-3 (HPC)
./projects/calibration-updates-2026/scripts/assess_possum_1934s.sh \
	--manifest ./projects/calibration-updates-2026/manifests/sb_manifest_reffield_average.txt

# Stage-4 (local or HPC)
./projects/calibration-updates-2026/scripts/copy_and_combine_assessment_results.sh \
	--manifest ./projects/calibration-updates-2026/manifests/sb_manifest_reffield_average.txt
```

### For users other than `raj030`

Before running on your environment, update paths and access settings in your manifest and/or script options:

- `REMOTE` (your HPC login/host)
- `REMOTE_BASE_ROOT` and ODC paths matching your project storage
- `LOCAL_BASE` (your local destination)
- Any module/environment requirements needed for `schedblock`/ASKAP tooling

Prefer overriding via manifest `KEY=VALUE` entries and CLI arguments rather than hard-coding user-specific paths in scripts.

### Release tag checklist (recommended)

Before creating a release tag (for example `3.4`):

1. Ensure `CHANGELOG.md` has an entry for that exact version.
2. Merge release changes from `develop` into `main`.
3. Create and push an annotated tag from the release commit on `main`.

If you discover issues *before public release consumption*, you may move the same tag to a newer commit:

```bash
git tag -f 3.4 <new-commit>
git push origin 3.4 --force
```

If the release is already public/consumed, do **not** move the existing tag; publish a new patch version (for example `3.4.1`).


