#!/usr/bin/env python

from setuptools import setup

with open('README') as readme:
    documentation = readme.read()

setup(
    name = 'jsonfs',
    version = '0.1',

    description = 'JSON FS',
    long_description = documentation,

    author = 'Caleb Case',
    author_email = 'calebcase@gmail.com',

    maintainer = 'Caleb Case',
    maintainer_email = 'calebcase@gmail.com',

    license = 'LGPLv3+',
    py_modules=['jsonfs'],
    url = 'http://github.com/calebcase/jsonfs',

    classifiers = [
        'Development Status :: 2 - Pre-Alpha',
        'Intended Audience :: System Administrators',
        'License :: OSI Approved :: GNU Lesser General Public License v3 or later (LGPLv3+)',
        'Operating System :: MacOS',
        'Operating System :: POSIX',
        'Operating System :: Unix',
        'Programming Language :: Python :: 2',
        'Topic :: System :: Filesystems',
    ],

    install_requires = ['fusepy']
)
