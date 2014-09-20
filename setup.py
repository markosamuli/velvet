#!/usr/bin/env python

from __future__ import with_statement

import sys

from setuptools import setup, find_packages
from velvet import __version__

if sys.version_info <= (2, 5):
    error = "ERROR: velvet requires Python Version 2.5 or above...exiting."
    print >> sys.stderr, error
    sys.exit(1)

def readme():
    with open("README.rst") as f:
        return f.read()    

setup(
    name='velvet',
    version=__version__,
    packages = find_packages(),

    scripts=[
        'bin/velvet-config',
        'bin/velvet-cloudformation',
    ],

    install_requires=[
        'boto>=2.28.0', 
        'Fabric>=1.8.2',
        'python-dateutil>=2.2',
        'semantic-version>=2.3.0',
        'PyYAML>=3.10',
        'glob2>=0.4.1',
        'jenkinsapi>=0.2.20',
    ],

    author = 'Marko Kirves',
    author_email = 'marko.kirves@thisisdare.com',
    description='AWS API and Fabric tasks for deploying applications into EC2 instances',
    long_description=readme(),
    url='https://github.com/markosamuli/velvet',
)