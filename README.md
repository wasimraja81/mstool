# bptool  
This directory contains tools for ASKAP table analysis. 
* `bin` - contains python scripts for ASKAP ms table query/analysis, and continuum removal.
* `src` - Fortran codes for poly-harm fitting - used for continuum removal per baseline per timeStamp.
* `doc` - Historical folder containing a ppt describing the various mstool features and tools.

The required fortran libraries are built and the scripts installed in the system default directories with the fortran libraries properly linked. 
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


