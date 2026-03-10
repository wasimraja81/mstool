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
askapdev>$ git clone ssh://git@bitbucket.csiro.au:7999/~raj030/mstool.git
askapdev>$ cd mstool
askapuser>$ pip3 install -e .
```
This will build the fortran libraries, and install the scripts in `/usr/local/bin` in a unix system.

### Run a test
```
askapuser>$ msInfo.py -h
```

### Project-specific workflow (calibration updates)

Recommended linkage:
1) process refField
2) process 1934s
3) run assessment script on HPC
4) copy+combine from local machine once steps 1, 2 and 3 are complete

```
askapuser>$ sbatch ./projects/calibration-updates-2026/slurm/start_refField.slurm \
	--manifest ./projects/calibration-updates-2026/manifests/sb_manifest_reffield_average.txt

askapuser>$ sbatch ./projects/calibration-updates-2026/slurm/start_1934s.slurm \
	--manifest ./projects/calibration-updates-2026/manifests/sb_manifest_reffield_average.txt

askapuser>$ ./projects/calibration-updates-2026/scripts/assess_possum_1934s.sh \
	--manifest ./projects/calibration-updates-2026/manifests/sb_manifest_reffield_average.txt

askapuser>$ ./projects/calibration-updates-2026/scripts/copy_and_combine_assessment_results.sh \
	--manifest ./projects/calibration-updates-2026/manifests/sb_manifest_reffield_average.txt
```


