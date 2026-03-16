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

### Projects

| Project | Description |
|---------|-------------|
| [`projects/calibration-updates-2026`](projects/calibration-updates-2026/README.md) | Calibration updates using reference fields — 4-stage HPC pipeline, leakage diagnostics, PAF visualisation tools |

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


