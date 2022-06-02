#!/usr/bin/env python
# -*- coding: utf-8 -*-
from numpy.distutils.core import setup, Extension
import os
import io

# Package meta-data.
NAME = 'mstool'
DESCRIPTION = 'Python scripts to analyse ASKAP ms tables.'
URL = 'https://bitbucket.csiro.au/users/raj030/repos/mstool'
EMAIL = 'wasim.raja@csiro.au'
AUTHOR = 'Wasim Raja'
REQUIRES_PYTHON = '>=3.6.0'
VERSION = '2.0'

# What packages are required for this module to be executed?
REQUIRED = [
    'python-casacore', 'six', 'matplotlib', 'astropy'
]

module1 = Extension(name='finterp_mstool',
                sources=['mstool/src/fpython/finterp.f'],
                extra_f90_compile_args=["-ffixed-form"]
                )
module2 = Extension(name='process_bptab_mstool',
                sources=['mstool/src/fpython/process_bptab.f'],
                extra_f90_compile_args=["-ffixed-form"]
                )
module3 = Extension(name='meanrms_mstool',
                sources=['mstool/src/fpython/robust_meanrms.f'],
                extra_f90_compile_args=["-ffixed-form"]
                )

here = os.path.abspath(os.path.dirname(__file__))

# Import the README and use it as the long-description.
# Note: this will only work if 'README.md' is present in your MANIFEST.in file!
try:
    with io.open(os.path.join(here, 'README.md'), encoding='utf-8') as f:
        long_description = '\n' + f.read()
except FileNotFoundError:
    long_description = DESCRIPTION

# Load the package's __version__.py module as a dictionary.
about = {}
if not VERSION:
    project_slug = NAME.lower().replace("-", "_").replace(" ", "_")
    with open(os.path.join(here, project_slug, '__version__.py')) as f:
        exec(f.read(), about)
else:
    about['__version__'] = VERSION

setup(
    name=NAME,
    version=about['__version__'],
    description=DESCRIPTION,
    long_description=long_description,
    long_description_content_type='text/markdown',
    author=AUTHOR,
    author_email=EMAIL,
    python_requires=REQUIRES_PYTHON,
    url=URL,
    packages=['mstool'],
    scripts=[
            'mstool/bin/msInfo.py',
            'mstool/bin/remUVcont.py',
            'mstool/bin/sniffMS.py',
            'mstool/bin/sniffUVW.py',
            'mstool/bin/fixDir.py',
        ],
    install_requires=REQUIRED,
    ext_modules=[module1,module2,module3],
    include_package_data=True,
    license='BSD',
    classifiers=[
        # Trove classifiers
        # Full list: https://pypi.python.org/pypi?%3Aaction=list_classifiers
        'License :: OSI Approved :: BSD License',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: Implementation :: CPython',
        'Programming Language :: Python :: Implementation :: PyPy'
    ]
)

